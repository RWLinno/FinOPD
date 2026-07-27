"""Dependence-aware uncertainty and multiple-comparison utilities."""
from __future__ import annotations

from typing import Mapping

import numpy as np

from finvl.evaluation.metrics import sharpe_ratio


def moving_block_bootstrap_sharpe(
    returns: np.ndarray,
    *,
    block_size: int = 20,
    samples: int = 2000,
    seed: int = 42,
    confidence: float = 0.95,
) -> dict[str, float]:
    """Percentile CI for Sharpe while preserving local serial dependence."""
    x = np.asarray(returns, dtype=float)
    if len(x) < max(3, block_size):
        raise ValueError("return series is shorter than one bootstrap block")
    rng = np.random.default_rng(seed)
    starts = np.arange(len(x) - block_size + 1)
    estimates = np.empty(samples)
    blocks_needed = int(np.ceil(len(x) / block_size))
    for i in range(samples):
        draw = rng.choice(starts, size=blocks_needed, replace=True)
        sample = np.concatenate([x[j : j + block_size] for j in draw])[: len(x)]
        estimates[i] = sharpe_ratio(sample)
    alpha = 1.0 - confidence
    return {
        "estimate": sharpe_ratio(x),
        "ci_low": float(np.nanquantile(estimates, alpha / 2)),
        "ci_high": float(np.nanquantile(estimates, 1 - alpha / 2)),
        "block_size": block_size,
        "samples": samples,
        "seed": seed,
    }


def holm_adjust(p_values: Mapping[str, float]) -> dict[str, float]:
    """Holm family-wise-error adjustment for named comparisons."""
    ordered = sorted(p_values.items(), key=lambda item: item[1])
    adjusted: dict[str, float] = {}
    running = 0.0
    m = len(ordered)
    for rank, (name, p_value) in enumerate(ordered):
        running = max(running, min(1.0, (m - rank) * float(p_value)))
        adjusted[name] = running
    return adjusted
