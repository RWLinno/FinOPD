"""
GRPO-lite: Group Relative Policy Optimization for the Factor Router.
Uses trajectory-level advantage (J - mean(J)) as reward signal
for discrete factor selection without a critic network.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

import torch
import torch.nn as nn
import torch.optim as optim

logger = logging.getLogger(__name__)


class GRPOLiteUpdater:
    """
    GRPO-lite optimizer for the factor router.
    No critic needed: uses batch-normalized trajectory returns as advantage.
    """

    def __init__(
        self,
        lr: float = 1e-4,
        clip_eps: float = 0.2,
        entropy_coef: float = 0.01,
    ):
        self.lr = lr
        self.clip_eps = clip_eps
        self.entropy_coef = entropy_coef
        self.optimizer = None

    def setup(self, router: nn.Module):
        """Initialize optimizer for the router."""
        self.optimizer = optim.Adam(router.parameters(), lr=self.lr)

    def update(
        self,
        router: nn.Module,
        geometry_embeddings: torch.Tensor,
        regime_onehots: torch.Tensor,
        trajectory_returns: torch.Tensor,
        old_logits: Optional[torch.Tensor] = None,
    ) -> Dict[str, float]:
        """
        Single GRPO-lite update step.
        
        Args:
            router: FactorRouter module
            geometry_embeddings: (batch, geo_dim)
            regime_onehots: (batch, 4)
            trajectory_returns: (batch,) raw returns J
            old_logits: (batch, num_factors) logits from previous policy
        """
        if self.optimizer is None:
            self.setup(router)

        advantages = trajectory_returns - trajectory_returns.mean()
        std = trajectory_returns.std()
        if std > 1e-8:
            advantages = advantages / std

        router.train()
        selection, logits = router(geometry_embeddings, regime_onehots, hard=False)

        log_probs = torch.log_softmax(logits, dim=-1)
        selected_log_probs = (log_probs * selection).sum(dim=-1)

        if old_logits is not None:
            old_log_probs = torch.log_softmax(old_logits, dim=-1)
            old_selected = (old_log_probs * selection.detach()).sum(dim=-1)
            ratio = (selected_log_probs - old_selected.detach()).exp()
            clipped_ratio = ratio.clamp(1 - self.clip_eps, 1 + self.clip_eps)
            policy_loss = -torch.min(ratio * advantages, clipped_ratio * advantages).mean()
        else:
            policy_loss = -(selected_log_probs * advantages).mean()

        probs = torch.softmax(logits, dim=-1)
        entropy = -(probs * (probs + 1e-8).log()).sum(dim=-1).mean()
        entropy_loss = -self.entropy_coef * entropy

        loss = policy_loss + entropy_loss

        self.optimizer.zero_grad()
        loss.backward()
        nn.utils.clip_grad_norm_(router.parameters(), 1.0)
        self.optimizer.step()

        return {
            "policy_loss": policy_loss.item(),
            "entropy": entropy.item(),
            "mean_advantage": advantages.mean().item(),
            "total_loss": loss.item(),
        }
