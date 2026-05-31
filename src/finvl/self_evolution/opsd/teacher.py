"""
Teacher module for OPSD.
Teacher shares LoRA weights with student but receives hindsight information
(serialized risk-adjusted returns) as privileged context.
Teacher weights are frozen throughout training.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import torch

logger = logging.getLogger(__name__)


class OPSDTeacher:
    """
    Teacher for On-Policy Self-Distillation.
    - Shares initial LoRA checkpoint with student
    - Receives hindsight prefix with realized returns
    - Weights frozen during entire training
    """

    def __init__(
        self,
        model_path: str,
        lora_path: str,
        hindsight_prefix: str = "[HINDSIGHT]",
        device: str = "cuda",
    ):
        self.model_path = model_path
        self.lora_path = lora_path
        self.hindsight_prefix = hindsight_prefix
        self.device = device
        self.model = None

    def load(self):
        """Load teacher model with frozen LoRA weights."""
        try:
            from swift.llm import PtEngine
            self.model = PtEngine(self.model_path, adapters=[self.lora_path])
            logger.info(f"Teacher loaded: {self.model_path} + {self.lora_path}")
        except ImportError:
            logger.warning("ms-swift not available, using placeholder teacher")
            self.model = None

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
    ) -> List[torch.Tensor]:
        """
        Teacher forward pass with hindsight.
        Returns logits distributions for each position in the trajectory.
        """
        if realized_returns:
            prompts = [
                self.build_hindsight_prompt(p, r)
                for p, r in zip(prompts, realized_returns)
            ]

        if self.model is None:
            batch_size = len(prompts)
            return [torch.randn(1, 100, 32000) for _ in range(batch_size)]

        logits_list = []
        for prompt in prompts:
            messages = [{"role": "user", "content": prompt}]
            with torch.no_grad():
                output = self.model.infer(messages=messages, images=images)
            logits_list.append(output)

        return logits_list
