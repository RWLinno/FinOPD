"""
Result analysis for FinVL-MAS experiments.
Regime-conditioned analysis, agent contribution tracking, and result formatting.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from finvl.evaluation.metrics import compute_all_metrics
from finvl.visual.geometry import GeometryExtractor


class RegimeAnalyzer:
    """Analyze performance conditioned on market regime."""

    def __init__(self):
        self.extractor = GeometryExtractor()

    def classify_dates(
        self, ohlcv_df: pd.DataFrame, window: int = 20
    ) -> pd.Series:
        """Classify each date into a regime based on trailing window."""
        regimes = []
        for i in range(len(ohlcv_df)):
            start = max(0, i - window + 1)
            sub = ohlcv_df.iloc[start: i + 1]
            if len(sub) < 10:
                regimes.append("quiet")
                continue
            regime_state = self.extractor.classify_regime(sub)
            regimes.append(regime_state.regime.value)
        return pd.Series(regimes, index=ohlcv_df.index)

    def regime_conditioned_metrics(
        self,
        returns: np.ndarray,
        dates: pd.DatetimeIndex,
        regimes: pd.Series,
    ) -> Dict[str, Dict[str, float]]:
        """Compute metrics per regime."""
        results = {}
        for regime in regimes.unique():
            mask = regimes.reindex(dates).values == regime
            # align to returns (which are 1 shorter than dates in some cases)
            mask_aligned = mask[: len(returns)]
            regime_returns = returns[mask_aligned]
            if len(regime_returns) < 5:
                continue
            results[regime] = compute_all_metrics(regime_returns)
            results[regime]["num_days"] = int(mask_aligned.sum())
        return results


def format_metrics_table(
    results: Dict[str, Dict[str, float]],
    metrics_to_show: Optional[List[str]] = None,
) -> str:
    """Format a metrics dict-of-dicts as a markdown table."""
    if not results:
        return "No results to display."

    if metrics_to_show is None:
        metrics_to_show = [
            "sharpe_ratio", "annualized_return", "max_drawdown",
            "directional_accuracy", "win_rate", "num_trades",
        ]

    header = "| Method | " + " | ".join(metrics_to_show) + " |"
    sep = "|" + "|".join(["---"] * (len(metrics_to_show) + 1)) + "|"
    rows = [header, sep]

    for name, metrics in results.items():
        vals = []
        for m in metrics_to_show:
            v = metrics.get(m, 0.0)
            if isinstance(v, float):
                if "pct" in m or "return" in m or "drawdown" in m or "accuracy" in m or "rate" in m:
                    vals.append(f"{v:.2%}")
                else:
                    vals.append(f"{v:.4f}")
            else:
                vals.append(str(v))
        rows.append(f"| {name} | " + " | ".join(vals) + " |")

    return "\n".join(rows)
