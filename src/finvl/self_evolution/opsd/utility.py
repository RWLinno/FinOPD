"""Outcome utility used by routing, memory admission, and agent credit."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from finvl.evaluation.metrics import max_drawdown, sharpe_ratio


@dataclass(frozen=True)
class UtilityConfig:
    return_weight: float = 1.0
    drawdown_weight: float = 0.5
    cvar_weight: float = 0.5
    turnover_weight: float = 0.1
    cvar_alpha: float = 0.05


def outcome_utility(
    returns: np.ndarray,
    turnover: float,
    config: UtilityConfig = UtilityConfig(),
) -> dict[str, float]:
    """Compute the single normalized utility used throughout FinOPD.

    Return and downside terms are expressed on the same decimal scale. CVaR is
    reported as a non-negative loss. No annualized ratio enters the reward.
    """
    values = np.asarray(returns, dtype=float)
    if values.ndim != 1 or not len(values) or not np.isfinite(values).all():
        raise ValueError("returns must be a non-empty finite 1-D array")
    cumulative_return = float(np.prod(1.0 + values) - 1.0)
    drawdown = max_drawdown(values)
    cutoff = float(np.quantile(values, config.cvar_alpha))
    tail = values[values <= cutoff]
    cvar_loss = float(max(0.0, -tail.mean()))
    utility = (
        config.return_weight * cumulative_return
        - config.drawdown_weight * drawdown
        - config.cvar_weight * cvar_loss
        - config.turnover_weight * float(turnover)
    )
    return {
        "utility": float(utility),
        "cumulative_return": cumulative_return,
        "sharpe": sharpe_ratio(values),
        "mdd": drawdown,
        "cvar_loss": cvar_loss,
        "turnover": float(turnover),
    }
