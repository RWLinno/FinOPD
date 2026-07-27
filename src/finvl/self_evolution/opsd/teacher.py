"""
Teacher module for OPSD.
Compatibility inference wrapper for the frozen hindsight teacher.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class OPSDTeacher:
    """
    Teacher for On-Policy Self-Distillation.
    - Uses a distinct Qwen3.5-27B checkpoint
    - Receives hindsight prefix with realized returns
    - Weights frozen during entire training
    """

    def __init__(
        self,
        model_path: str,
        lora_path: str | None = None,
        hindsight_prefix: str = "[HINDSIGHT]",
        device: str = "cuda",
    ):
        self.model_path = model_path
        self.lora_path = lora_path
        self.hindsight_prefix = hindsight_prefix
        self.device = device
        self.model = None

    def load(self):
        """Load the teacher through the current ms-swift inference API."""
        try:
            from swift.infer_engine import TransformersEngine

            adapters = [self.lora_path] if self.lora_path else None
            self.model = TransformersEngine(
                self.model_path,
                adapters=adapters,
                device_map=self.device,
            )
            logger.info("Teacher loaded: %s", self.model_path)
        except ImportError as exc:
            raise RuntimeError("ms-swift is required for an evidence-bearing OPD run") from exc

    def build_hindsight_prompt(
        self,
        base_prompt: str,
        realized_returns: Dict[str, float],
    ) -> str:
        """Prepend hindsight information to the teacher prompt."""
        hindsight_str = " ".join(
            f"{k}={v:.4f}" for k, v in realized_returns.items()
        )
        return f"{self.hindsight_prefix} {hindsight_str}\n{base_prompt}"

    def forward(
        self,
        prompts: List[str],
        images: Optional[List[str]] = None,
        realized_returns: Optional[List[Dict[str, float]]] = None,
    ) -> List[object]:
        """
        Generate frozen-teacher annotations with token log-probability metadata.

        Full-vocabulary differentiable logits for training are provided by
        ``LocalQwenOPSDBackend``; this method is for inference/protocol audits.
        """
        if realized_returns:
            prompts = [
                self.build_hindsight_prompt(p, r)
                for p, r in zip(prompts, realized_returns)
            ]

        if self.model is None:
            raise RuntimeError("teacher must be loaded before forward()")

        from swift.infer_engine import InferRequest, RequestConfig

        requests = []
        for index, prompt in enumerate(prompts):
            request_images = []
            if images and index < len(images) and images[index]:
                request_images = [images[index]]
            requests.append(
                InferRequest(
                    messages=[{"role": "user", "content": prompt}],
                    images=request_images,
                )
            )
        return self.model.infer(
            requests,
            RequestConfig(
                max_tokens=128,
                temperature=0.0,
                logprobs=True,
                top_logprobs=20,
            ),
        )
