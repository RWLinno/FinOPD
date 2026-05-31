"""
JSD Loss: Generalized Jensen-Shannon Divergence with per-token KL clipping.
Core distillation objective for On-Policy Self-Distillation.
"""
from __future__ import annotations

import torch
import torch.nn.functional as F


def jsd_loss(
    logits_teacher: torch.Tensor,
    logits_student: torch.Tensor,
    beta: float = 0.5,
    temperature: float = 1.0,
) -> torch.Tensor:
    """
    Generalized JSD: JSD(p_T, p_S, beta).
    JSD = beta * KL(M || p_T) + (1-beta) * KL(M || p_S)
    where M = beta * p_T + (1-beta) * p_S
    """
    p_t = F.softmax(logits_teacher / temperature, dim=-1)
    p_s = F.softmax(logits_student / temperature, dim=-1)

    m = beta * p_t + (1 - beta) * p_s

    kl_t = F.kl_div(m.log(), p_t, reduction="none").sum(dim=-1)
    kl_s = F.kl_div(m.log(), p_s, reduction="none").sum(dim=-1)

    jsd = beta * kl_t + (1 - beta) * kl_s
    return jsd


def per_token_kl_clip(
    logits_teacher: torch.Tensor,
    logits_student: torch.Tensor,
    cap: float = 5.0,
    temperature: float = 1.0,
) -> torch.Tensor:
    """
    Per-token KL divergence with clipping to prevent stylistic tokens
    from dominating the gradient signal.
    """
    log_p_t = F.log_softmax(logits_teacher / temperature, dim=-1)
    log_p_s = F.log_softmax(logits_student / temperature, dim=-1)
    p_t = log_p_t.exp()

    kl = (p_t * (log_p_t - log_p_s)).sum(dim=-1)
    kl_clipped = kl.clamp(max=cap)
    return kl_clipped


def opsd_loss(
    logits_teacher: torch.Tensor,
    logits_student: torch.Tensor,
    beta: float = 0.5,
    kl_cap: float = 5.0,
    temperature: float = 1.0,
    token_weights: torch.Tensor = None,
) -> torch.Tensor:
    """
    Combined OPSD loss: JSD + clipped KL regularization.
    
    Args:
        logits_teacher: (batch, seq_len, vocab) teacher logits
        logits_student: (batch, seq_len, vocab) student logits
        beta: JSD interpolation weight
        kl_cap: per-token KL clipping threshold
        temperature: softmax temperature
        token_weights: (batch, seq_len) optional per-token weights from Shapley
    """
    jsd = jsd_loss(logits_teacher, logits_student, beta, temperature)
    kl_reg = per_token_kl_clip(logits_teacher, logits_student, kl_cap, temperature)

    loss = jsd + 0.1 * kl_reg

    if token_weights is not None:
        loss = loss * token_weights

    return loss.mean()
