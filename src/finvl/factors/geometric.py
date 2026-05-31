"""
Geometric factors derived from chart geometry analysis.
Converts structured geometry (formations, trend lines, S/R levels)
into numerical factor values for the router.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def formation_payoff(geometry: Dict[str, Any], close: float) -> float:
    """Expected payoff from detected chart formations."""
    formations = geometry.get("chart_formations", [])
    if not formations:
        return 0.0
    payoffs = []
    for f in formations:
        if isinstance(f, dict):
            target = f.get("target_price", close)
            payoffs.append((target - close) / max(close, 1e-6))
        else:
            payoffs.append(0.0)
    return float(np.mean(payoffs)) if payoffs else 0.0


def trend_consistency_vote(geometry: Dict[str, Any]) -> float:
    """Voting score from trend line directions."""
    trend_lines = geometry.get("trend_lines", [])
    if not trend_lines:
        return 0.0
    votes = []
    for tl in trend_lines:
        if isinstance(tl, dict):
            slope = tl.get("slope", 0.0)
            votes.append(np.sign(slope))
        else:
            votes.append(0.0)
    return float(np.mean(votes)) if votes else 0.0


def normalized_sr_distance(geometry: Dict[str, Any], close: float) -> float:
    """Normalized distance to nearest support/resistance level."""
    levels = geometry.get("price_levels", [])
    if not levels or close <= 0:
        return 0.0
    distances = []
    for level in levels:
        price = level.get("price", level) if isinstance(level, dict) else float(level)
        distances.append((close - price) / close)
    if not distances:
        return 0.0
    nearest = min(distances, key=abs)
    return float(nearest)


def regime_conditioned_volatility(
    geometry: Dict[str, Any], df: pd.DataFrame
) -> float:
    """Volatility adjusted by detected regime."""
    regime = geometry.get("regime", "calm")
    if len(df) < 5:
        return 0.0
    vol = df["close"].pct_change().std() * np.sqrt(252)
    regime_multiplier = {
        "calm": 0.5,
        "ranging": 0.8,
        "trending": 1.0,
        "volatile": 1.5,
    }.get(regime, 1.0)
    return float(vol * regime_multiplier)


def compute_geometric_factors(
    geometry: Dict[str, Any], df: pd.DataFrame
) -> Dict[str, float]:
    """Compute all geometric factors from chart geometry output."""
    close = float(df["close"].iloc[-1]) if len(df) > 0 else 0.0

    return {
        "geo_formation_payoff": formation_payoff(geometry, close),
        "geo_trend_vote": trend_consistency_vote(geometry),
        "geo_sr_distance": normalized_sr_distance(geometry, close),
        "geo_regime_vol": regime_conditioned_volatility(geometry, df),
        "geo_num_patterns": float(len(geometry.get("candle_patterns", []))),
        "geo_num_formations": float(len(geometry.get("chart_formations", []))),
        "geo_trend_count": float(len(geometry.get("trend_lines", []))),
        "geo_volume_signal_count": float(len(geometry.get("volume_signals", []))),
    }
