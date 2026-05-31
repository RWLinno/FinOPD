"""
Parser for VLM chart analysis responses.
Converts raw VLM JSON output into typed ChartGeometry.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from finvl.core.types import (
    CandlePattern,
    ChartFormation,
    ChartGeometry,
    FormationStage,
    Implication,
    PatternSignificance,
    PriceLevel,
    RegimeState,
    RegimeType,
    TrendDirection,
    TrendLine,
    VolumeSignal,
)

logger = logging.getLogger(__name__)


def parse_vlm_chart_analysis(data: Dict[str, Any]) -> ChartGeometry:
    """Convert VLM JSON response to ChartGeometry."""
    if data.get("parse_error") or data.get("error"):
        logger.warning(f"VLM returned error/unparseable: {data.get('error', 'parse_error')}")
        return ChartGeometry(confidence=0.0, narrative=data.get("raw", ""))

    # Unwrap nested response (VLM may wrap in "analysis" or "chart_analysis")
    if "analysis" in data and isinstance(data["analysis"], dict):
        data = data["analysis"]
    elif "chart_analysis" in data and isinstance(data["chart_analysis"], dict):
        data = data["chart_analysis"]

    geometry = ChartGeometry()

    # Trendlines
    for tl in data.get("trendlines", []):
        if not isinstance(tl, dict):
            continue
        dir_str = tl.get("direction", tl.get("type", "up")).lower()
        direction = TrendDirection.DOWN if "down" in dir_str else TrendDirection.UP
        slope_val = tl.get("slope", 0)
        if isinstance(slope_val, str):
            slope_map = {"steep": 0.8, "moderate": 0.5, "gentle": 0.2, "flat": 0.0}
            slope_val = slope_map.get(slope_val.lower(), 0.5)
        geometry.trendlines.append(TrendLine(
            direction=direction,
            slope=float(slope_val),
            intercept=0.0,
            status=tl.get("status", "intact"),
            confidence=float(tl.get("confidence", 0.5)) if isinstance(tl.get("confidence"), (int, float)) else 0.5,
        ))

    # Support/Resistance
    for sr in data.get("support_resistance", []):
        price = float(sr.get("price", sr.get("level", 0)))
        geometry.support_resistance.append(PriceLevel(
            price=price,
            level_type=sr.get("type", "support"),
            strength=float(sr.get("strength", 0.5)) if isinstance(sr.get("strength"), (int, float)) else 0.5,
            touch_count=int(sr.get("touch_count", 1)),
        ))

    # Candlestick patterns
    for cp in data.get("candlestick_patterns", []):
        if not isinstance(cp, dict):
            continue
        impl = _parse_implication(cp.get("implication", "neutral"))
        sig = _parse_significance(cp.get("significance", cp.get("confidence", "moderate")))
        geometry.candlestick_patterns.append(CandlePattern(
            pattern=cp.get("pattern", "unknown"),
            significance=sig,
            implication=impl,
        ))

    # Formations
    for f in data.get("formations", data.get("chart_formations", [])):
        if isinstance(f, dict):
            stage_map = {"forming": FormationStage.FORMING, "confirmed": FormationStage.CONFIRMED,
                         "broken": FormationStage.BROKEN}
            geometry.formations.append(ChartFormation(
                formation_type=f.get("type", f.get("formation", "unknown")),
                stage=stage_map.get(f.get("stage", "forming"), FormationStage.FORMING),
                target_price=f.get("target_price"),
                confidence=float(f.get("confidence", 0.5)) if isinstance(f.get("confidence"), (int, float)) else 0.5,
            ))

    # Volume signals
    for vs in data.get("volume_signals", data.get("volume_analysis", [])):
        if isinstance(vs, dict):
            geometry.volume_signals.append(VolumeSignal(
                signal_type=vs.get("type", vs.get("observation", "unknown")),
                implication=_parse_implication(vs.get("implication", vs.get("description", "neutral"))),
                description=vs.get("location", vs.get("description", "")),
            ))

    # Regime
    regime_data = data.get("regime", data.get("regime_assessment", {}))
    if isinstance(regime_data, str):
        regime_data = {"state": regime_data}
    regime_map = {
        "trending_up": RegimeType.TRENDING_UP, "trending_down": RegimeType.TRENDING_DOWN,
        "trending": RegimeType.TRENDING_UP, "ranging": RegimeType.RANGING,
        "volatile": RegimeType.VOLATILE, "quiet": RegimeType.QUIET,
        "transitioning": RegimeType.TRANSITIONING,
    }
    state_str = regime_data.get("state", regime_data.get("type", "ranging")) if isinstance(regime_data, dict) else "ranging"
    geometry.regime = RegimeState(
        regime=regime_map.get(state_str.lower(), RegimeType.RANGING),
        trend_strength=float(regime_data.get("trend_strength", 0.5)) if isinstance(regime_data, dict) and isinstance(regime_data.get("trend_strength"), (int, float)) else 0.5,
        volatility_percentile=0.5,
    )

    bias_val = data.get("overall_bias", data.get("bias", "neutral"))
    geometry.overall_bias = _parse_implication(bias_val if isinstance(bias_val, str) else "neutral")
    conf_val = data.get("confidence", 0.5)
    geometry.confidence = float(conf_val) if isinstance(conf_val, (int, float)) else 0.5
    geometry.narrative = data.get("narrative", data.get("summary", ""))
    return geometry


def _parse_implication(s: str) -> Implication:
    s = s.lower().strip()
    if "bull" in s:
        return Implication.BULLISH
    if "bear" in s:
        return Implication.BEARISH
    return Implication.NEUTRAL


def _parse_significance(s: str) -> PatternSignificance:
    s = s.lower().strip()
    if "strong" in s:
        return PatternSignificance.STRONG
    if "weak" in s:
        return PatternSignificance.WEAK
    return PatternSignificance.MODERATE
