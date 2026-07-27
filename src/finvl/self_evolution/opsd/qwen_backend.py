"""Local Qwen3.5 student/teacher backend for evidence-bearing OPSD runs."""
from __future__ import annotations

import copy
import json
import logging
import re
from pathlib import Path
from typing import Dict

import numpy as np
import torch
import torch.nn.functional as F

from finvl.core.types import Action, Conviction, DecisionOutput
from finvl.self_evolution.opsd.jsd import opsd_loss
from finvl.self_evolution.opsd.rollout import Trajectory

logger = logging.getLogger(__name__)


class QwenPolicyOrchestrator:
    """Use structured specialists as evidence and Qwen3.5-9B as final policy."""

    def __init__(self, base_orchestrator, backend, decision_enabled: bool = True):
        self.base_orchestrator = base_orchestrator
        self.backend = backend
        self.decision_enabled = decision_enabled
        self.last_policy_prompt = ""
        self.last_policy_completion = ""

    @property
    def last_factor_ids(self):
        return self.base_orchestrator.last_factor_ids

    @property
    def last_router_features(self):
        return self.base_orchestrator.last_router_features

    @property
    def last_router_regime(self):
        return self.base_orchestrator.last_router_regime

    @property
    def last_router_selected_indices(self):
        return self.base_orchestrator.last_router_selected_indices

    @property
    def factor_router(self):
        return self.base_orchestrator.factor_router

    @property
    def router_factor_names(self):
        return self.base_orchestrator.router_factor_names

    async def run(self, inputs) -> DecisionOutput:
        base_decision = await self.base_orchestrator.run(inputs)
        if not self.decision_enabled:
            self.last_policy_prompt = ""
            self.last_policy_completion = ""
            return DecisionOutput(
                action=Action.HOLD,
                conviction=Conviction.LOW,
                position_size_pct=0.0,
                confidence=1.0,
                rationale="Decision policy disabled for coalition replay",
            )

        prompt = self.backend.build_policy_prompt(
            inputs,
            base_decision,
            self.base_orchestrator.get_reasoning_trace(),
        )
        decision, completion = self.backend.generate_decision(prompt, base_decision)
        self.last_policy_prompt = prompt
        self.last_policy_completion = completion
        return decision


class LocalQwenOPSDBackend:
    """Train a 9B LoRA policy from a frozen 27B hindsight teacher.

    Student, round-start reference, and teacher distributions are evaluated on
    the identical student-generated completion. The teacher receives only a
    compact outcome summary after the trajectory horizon closes.
    """

    def __init__(
        self,
        student_model: str,
        teacher_model: str,
        lora_path: str | None = None,
        student_device: str = "cuda:0",
        teacher_device: str = "cuda:1",
        learning_rate: float = 2e-5,
        lora_rank: int = 16,
        target_modules: list[str] | None = None,
        beta: float = 0.5,
        kl_cap: float = 5.0,
        reference_kl_weight: float = 0.1,
        max_steps_per_trajectory: int = 8,
        max_new_tokens: int = 256,
    ):
        self.student_model_path = student_model
        self.teacher_model_path = teacher_model
        self.lora_path = lora_path
        self.student_device = student_device
        self.teacher_device = teacher_device
        self.learning_rate = learning_rate
        self.lora_rank = lora_rank
        self.target_modules = target_modules or ["q_proj", "v_proj", "o_proj"]
        self.beta = beta
        self.kl_cap = kl_cap
        self.reference_kl_weight = reference_kl_weight
        self.max_steps_per_trajectory = max_steps_per_trajectory
        self.max_new_tokens = max_new_tokens
        self.processor = None
        self.student = None
        self.teacher = None
        self.optimizer = None
        self._reference_adapter = None

    @staticmethod
    def _device_map(device: str):
        return {"": device}

    def load(self) -> None:
        from peft import LoraConfig, PeftModel, get_peft_model
        from transformers import AutoModelForImageTextToText, AutoProcessor

        dtype = torch.bfloat16
        self.processor = AutoProcessor.from_pretrained(self.student_model_path)
        student_base = AutoModelForImageTextToText.from_pretrained(
            self.student_model_path,
            dtype=dtype,
            device_map=self._device_map(self.student_device),
            low_cpu_mem_usage=True,
        )
        adapter_config = (
            Path(self.lora_path) / "adapter_config.json" if self.lora_path else None
        )
        if adapter_config and adapter_config.exists():
            self.student = PeftModel.from_pretrained(
                student_base,
                self.lora_path,
                is_trainable=True,
            )
        else:
            self.student = get_peft_model(
                student_base,
                LoraConfig(
                    r=self.lora_rank,
                    lora_alpha=2 * self.lora_rank,
                    lora_dropout=0.05,
                    target_modules=self.target_modules,
                    bias="none",
                ),
            )
        self.student.enable_input_require_grads()
        self.student.gradient_checkpointing_enable()

        self.teacher = AutoModelForImageTextToText.from_pretrained(
            self.teacher_model_path,
            dtype=dtype,
            device_map=self._device_map(self.teacher_device),
            low_cpu_mem_usage=True,
        )
        self.teacher.requires_grad_(False)
        self.teacher.eval()

        student_vocab = self.student.config.text_config.vocab_size
        teacher_vocab = self.teacher.config.text_config.vocab_size
        if student_vocab != teacher_vocab:
            raise ValueError(
                f"student/teacher vocab mismatch: {student_vocab} != {teacher_vocab}"
            )
        parameters = [parameter for parameter in self.student.parameters() if parameter.requires_grad]
        if not parameters:
            raise RuntimeError("student LoRA exposes no trainable parameters")
        self.optimizer = torch.optim.AdamW(parameters, lr=self.learning_rate)
        logger.info(
            "Loaded Qwen OPSD backend: student=%s teacher=%s trainable=%d",
            self.student_model_path,
            self.teacher_model_path,
            sum(parameter.numel() for parameter in parameters),
        )

    def wrap_orchestrator(self, orchestrator, decision_enabled: bool = True):
        return QwenPolicyOrchestrator(orchestrator, self, decision_enabled)

    def build_policy_prompt(self, inputs, base_decision, reasoning_trace: str) -> str:
        frame = inputs["ohlcv_df"].tail(20)
        close = frame["close"].astype(float)
        returns = close.pct_change().dropna()
        snapshot = {
            "asset": inputs.get("asset"),
            "date": inputs.get("end_date", str(frame.index[-1].date())),
            "current_price": round(float(close.iloc[-1]), 6),
            "return_1d": round(float(returns.iloc[-1]) if len(returns) else 0.0, 6),
            "return_5d": round(float(close.iloc[-1] / close.iloc[-6] - 1) if len(close) >= 6 else 0.0, 6),
            "volatility_20d": round(float(returns.std(ddof=1) * np.sqrt(252)) if len(returns) > 1 else 0.0, 6),
            "volume_last": round(float(frame["volume"].iloc[-1]), 2),
            "specialist_action": base_decision.action.value,
            "specialist_confidence": round(float(base_decision.confidence), 4),
            "specialist_rationale": base_decision.rationale,
            "reasoning_trace": reasoning_trace,
            "retrieved_matured_episodes": inputs.get("retrieved_episodes", []),
        }
        return (
            "You are the deployable FinOPD portfolio decision policy. Use only the "
            "point-in-time evidence below. Return exactly one compact JSON object, "
            "with no markdown or extra text, with action "
            "(buy/sell/hold), confidence in [0,1], position_size_pct in [0,0.30], "
            "conviction (low/moderate/high), rationale, key_evidence, and risks. "
            "confidence and position_size_pct must be JSON numbers, not strings.\n"
            + json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
        )

    def _prompt_ids(self, prompt: str, device: str) -> torch.Tensor:
        messages = [{"role": "user", "content": prompt}]
        ids = self.processor.tokenizer.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_tensors="pt",
            enable_thinking=False,
        )
        if hasattr(ids, "input_ids"):
            ids = ids.input_ids
        return ids.to(device)

    @staticmethod
    def _extract_json(text: str) -> Dict:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise ValueError("policy completion contains no JSON object")
        return json.loads(match.group(0))

    @staticmethod
    def _bounded_number(
        value,
        *,
        default: float,
        lower: float,
        upper: float,
        percent_if_gt_one: bool = False,
    ) -> float:
        """Parse a model-emitted scalar without discarding an otherwise valid JSON."""
        aliases = {"low": 0.25, "moderate": 0.5, "medium": 0.5, "high": 0.75}
        if isinstance(value, str) and value.strip().lower() in aliases:
            number = aliases[value.strip().lower()]
        else:
            try:
                number = float(value)
            except (TypeError, ValueError):
                number = float(default)
        if not np.isfinite(number):
            number = float(default)
        if percent_if_gt_one and number > 1.0:
            number /= 100.0
        return float(np.clip(number, lower, upper))

    def generate_decision(
        self, prompt: str, fallback: DecisionOutput
    ) -> tuple[DecisionOutput, str]:
        if self.student is None:
            raise RuntimeError("Qwen OPSD backend must be loaded before rollout")
        self.student.eval()
        input_ids = self._prompt_ids(prompt, self.student_device)
        with torch.inference_mode():
            output = self.student.generate(
                input_ids=input_ids,
                attention_mask=torch.ones_like(input_ids),
                max_new_tokens=self.max_new_tokens,
                do_sample=False,
                use_cache=True,
            )
        completion = self.processor.tokenizer.decode(
            output[0, input_ids.shape[1]:],
            skip_special_tokens=True,
        ).strip()
        try:
            parsed = self._extract_json(completion)
            action = Action(str(parsed.get("action", "hold")).lower())
            conviction = Conviction(str(parsed.get("conviction", "low")).lower())
            confidence = self._bounded_number(
                parsed.get("confidence"),
                default=fallback.confidence,
                lower=0.0,
                upper=1.0,
            )
            size = self._bounded_number(
                parsed.get("position_size_pct"),
                default=0.0,
                lower=0.0,
                upper=0.30,
                percent_if_gt_one=True,
            )
            if action == Action.HOLD:
                size = 0.0
            evidence = parsed.get("key_evidence", [])
            risks = parsed.get("risks", [])
            return DecisionOutput(
                action=action,
                conviction=conviction,
                position_size_pct=size,
                confidence=confidence,
                rationale=str(parsed.get("rationale", "")),
                key_evidence=evidence if isinstance(evidence, list) else [str(evidence)],
                risks_acknowledged=risks if isinstance(risks, list) else [str(risks)],
            ), completion
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            logger.warning("Invalid student policy JSON; using specialist fallback: %s", exc)
            return copy.deepcopy(fallback), completion

    def begin_iteration(self, _iteration: int) -> None:
        from peft.utils.save_and_load import get_peft_model_state_dict

        self._reference_adapter = {
            key: value.detach().cpu().clone()
            for key, value in get_peft_model_state_dict(self.student).items()
        }

    def _completion_ids(self, completion: str, device: str) -> torch.Tensor:
        ids = self.processor.tokenizer(
            completion,
            add_special_tokens=False,
            return_tensors="pt",
        ).input_ids[0]
        eos = torch.tensor([self.processor.tokenizer.eos_token_id], dtype=ids.dtype)
        return torch.cat([ids, eos]).to(device)

    @staticmethod
    def _completion_logits(model, prompt_ids, completion_ids):
        joined = torch.cat([prompt_ids[0], completion_ids]).unsqueeze(0)
        output = model(
            input_ids=joined,
            attention_mask=torch.ones_like(joined),
            use_cache=False,
        )
        start = prompt_ids.shape[1] - 1
        end = start + completion_ids.shape[0]
        return output.logits[:, start:end, :]

    def _reference_logits(self, prompt_ids, completion_ids):
        from peft.utils.save_and_load import (
            get_peft_model_state_dict,
            set_peft_model_state_dict,
        )

        current = {
            key: value.detach().cpu().clone()
            for key, value in get_peft_model_state_dict(self.student).items()
        }
        set_peft_model_state_dict(self.student, self._reference_adapter)
        self.student.eval()
        with torch.no_grad():
            logits = self._completion_logits(
                self.student, prompt_ids, completion_ids
            ).detach()
        set_peft_model_state_dict(self.student, current)
        return logits

    def update(self, trajectory: Trajectory, credits: Dict[str, float]) -> Dict[str, float]:
        if self._reference_adapter is None:
            raise RuntimeError("begin_iteration() must precede update()")
        candidates = [
            step for step in trajectory.steps
            if step.policy_prompt and step.policy_completion
        ]
        if not candidates:
            raise RuntimeError("trajectory contains no student-generated policy tokens")
        if len(candidates) > self.max_steps_per_trajectory:
            indices = np.linspace(
                0, len(candidates) - 1, self.max_steps_per_trajectory, dtype=int
            )
            candidates = [candidates[index] for index in indices]

        decision_weight = float(credits.get("DecisionPM", 0.0))
        if decision_weight <= 0.0:
            raise ValueError("DecisionPM distillation weight must be positive")
        losses = []
        reference_kls = []
        teacher_kls = []
        for step in candidates:
            completion_student = self._completion_ids(
                step.policy_completion, self.student_device
            )
            completion_teacher = completion_student.to(self.teacher_device)
            student_prompt = self._prompt_ids(step.policy_prompt, self.student_device)
            hindsight_fields = (
                "utility",
                "cumulative_return",
                "mdd",
                "cvar_loss",
                "turnover",
            )
            hindsight = json.dumps(
                {
                    key: trajectory.metrics[key]
                    for key in hindsight_fields
                    if key in trajectory.metrics
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            teacher_prompt = self._prompt_ids(
                f"[HINDSIGHT] {hindsight}\n{step.policy_prompt}",
                self.teacher_device,
            )

            reference_logits = self._reference_logits(
                student_prompt, completion_student
            )
            self.student.train()
            student_logits = self._completion_logits(
                self.student, student_prompt, completion_student
            )
            with torch.no_grad():
                teacher_logits = self._completion_logits(
                    self.teacher, teacher_prompt, completion_teacher
                ).to(self.student_device)

            distillation = opsd_loss(
                teacher_logits,
                student_logits,
                beta=self.beta,
                kl_cap=self.kl_cap,
            )
            student_log_probs = F.log_softmax(student_logits.float(), dim=-1)
            reference_probs = F.softmax(reference_logits.float(), dim=-1)
            reference_kl = (
                reference_probs
                * (reference_probs.clamp_min(1e-12).log() - student_log_probs)
            ).sum(dim=-1).mean()
            teacher_probs = F.softmax(teacher_logits.float(), dim=-1)
            teacher_kl = (
                teacher_probs
                * (teacher_probs.clamp_min(1e-12).log() - student_log_probs)
            ).sum(dim=-1).mean()
            loss = decision_weight * distillation + self.reference_kl_weight * reference_kl
            self.optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(
                [parameter for parameter in self.student.parameters() if parameter.requires_grad],
                1.0,
            )
            self.optimizer.step()
            self.student.eval()
            with torch.no_grad():
                updated_logits = self._completion_logits(
                    self.student, student_prompt, completion_student
                )
                updated_log_probs = F.log_softmax(updated_logits.float(), dim=-1)
                measured_reference_kl = (
                    reference_probs
                    * (
                        reference_probs.clamp_min(1e-12).log()
                        - updated_log_probs
                    )
                ).sum(dim=-1).mean()
            losses.append(float(loss.detach().cpu()))
            reference_kls.append(float(measured_reference_kl.detach().cpu()))
            teacher_kls.append(float(teacher_kl.detach().cpu()))

        return {
            "opsd_loss": float(np.mean(losses)),
            "reference_kl": float(np.mean(reference_kls)),
            "teacher_student_kl": float(np.mean(teacher_kls)),
            "distilled_steps": len(candidates),
        }

    def rollback(self) -> None:
        from peft.utils.save_and_load import set_peft_model_state_dict

        if self._reference_adapter is None:
            raise RuntimeError("no round-start adapter snapshot is available")
        set_peft_model_state_dict(self.student, self._reference_adapter)

    def save(self, output_dir: str) -> None:
        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)
        self.student.save_pretrained(output / "student_adapter")
