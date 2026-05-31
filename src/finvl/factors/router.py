"""
Factor Router: 2-layer MLP with Gumbel-Softmax top-k selection.
Input: (geometry_embedding, regime_onehot)
Output: factor ID list with selection probabilities
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger(__name__)


class FactorRouter(nn.Module):
    """
    Geometry-conditioned factor router.
    Uses Gumbel-Softmax for differentiable discrete factor selection.
    """

    def __init__(
        self,
        geometry_dim: int = 768,
        regime_dim: int = 4,
        num_factors: int = 170,
        hidden_dim: int = 256,
        top_k: int = 15,
        tau_start: float = 1.0,
        tau_end: float = 0.5,
    ):
        super().__init__()
        self.num_factors = num_factors
        self.top_k = top_k
        self.tau = tau_start
        self.tau_start = tau_start
        self.tau_end = tau_end

        input_dim = geometry_dim + regime_dim
        self.mlp = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(hidden_dim, num_factors),
        )

    def forward(
        self,
        geometry_embedding: torch.Tensor,
        regime_onehot: torch.Tensor,
        hard: bool = True,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Args:
            geometry_embedding: (batch, geometry_dim) from VLM last layer
            regime_onehot: (batch, 4) one-hot regime encoding
            hard: if True, use straight-through Gumbel-Softmax

        Returns:
            selection: (batch, num_factors) binary mask (top-k)
            logits: (batch, num_factors) raw logits for GRPO
        """
        x = torch.cat([geometry_embedding, regime_onehot], dim=-1)
        logits = self.mlp(x)

        if self.training:
            selection = self._gumbel_top_k(logits, self.top_k, self.tau, hard)
        else:
            _, indices = logits.topk(self.top_k, dim=-1)
            selection = torch.zeros_like(logits)
            selection.scatter_(1, indices, 1.0)

        return selection, logits

    def _gumbel_top_k(
        self, logits: torch.Tensor, k: int, tau: float, hard: bool
    ) -> torch.Tensor:
        """Differentiable top-k via repeated Gumbel-Softmax."""
        batch_size = logits.shape[0]
        selection = torch.zeros_like(logits)
        remaining_logits = logits.clone()

        for _ in range(k):
            gumbel_out = F.gumbel_softmax(remaining_logits, tau=tau, hard=hard)
            selection = selection + gumbel_out
            if hard:
                mask = (selection > 0.5).float()
                remaining_logits = remaining_logits - mask * 1e9
            else:
                remaining_logits = remaining_logits - gumbel_out * 1e4

        return selection.clamp(0, 1)

    def anneal_tau(self, progress: float):
        """Anneal temperature from tau_start to tau_end."""
        self.tau = self.tau_start + (self.tau_end - self.tau_start) * progress

    def get_selected_factor_ids(
        self, geometry_embedding: torch.Tensor, regime_onehot: torch.Tensor
    ) -> List[List[int]]:
        """Get selected factor indices for inference."""
        self.eval()
        with torch.no_grad():
            selection, _ = self.forward(geometry_embedding, regime_onehot, hard=True)
        return [sel.nonzero(as_tuple=True)[0].tolist() for sel in selection]

    def compute_entropy(self, logits: torch.Tensor) -> float:
        """Compute selection entropy for monitoring convergence."""
        probs = F.softmax(logits, dim=-1)
        entropy = -(probs * (probs + 1e-8).log()).sum(dim=-1).mean()
        return entropy.item()


REGIME_MAP = {"calm": 0, "ranging": 1, "trending": 2, "volatile": 3}


def encode_regime(regime: str) -> torch.Tensor:
    """Convert regime string to one-hot tensor."""
    idx = REGIME_MAP.get(regime, 0)
    onehot = torch.zeros(4)
    onehot[idx] = 1.0
    return onehot
