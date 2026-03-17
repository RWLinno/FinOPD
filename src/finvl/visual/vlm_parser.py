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

    geometry = ChartGeometry()

    # Trendlines
    for tl in data.get("trendlines", []):
        direction = TrendDirection.UP if tl.get("direction", "up") == "up" else TrendDirection.DOWN
        geometry.trendlines.append(TrendLine(
            direction=direction,
            slope=float(tl.get("slope", 0)),
            intercept=0.0,
            status=tl.get("status", "intact"),
            confidence=float(tl.get("confidence", 0.5)),
        ))

    # Support/Resistance
    for sr in data.get("support_resistance", []):
        geometry.support_resistance.append(PriceLevel(
            price=float(sr.get("price", 0)),
            level_type=sr.get("type", "support"),
            strength=float(sr.get("strength", 0.5)),
            touch_count=int(sr.get("touch_count", 1)),
        ))

    # Candlestick patterns
    for cp in data.get("candlestick_patterns", []):
        impl = _parse_implication(cp.get("implication", "neutral"))
        sig = _parse_significance(cp.get("significance", "moderate"))
        geometry.candlestick_patterns.append(CandlePattern(
            pattern=cp.get("pattern", "unknown"),
            significance=sig,
            implication=impl,
        ))

    # Formations
    for f in data.get("formations", []):
        stage_map = {"forming": FormationStage.FORMING, "confirmed": FormationStage.CONFIRMED,
                     "broken": FormationStage.BROKEN}
        geometry.formations.append(ChartFormation(
            formation_type=f.get("type", "unknown"),
            stage=stage_map.get(f.get("stage", "forming"), FormationStage.FORMING),
            target_price=f.get("target_price"),
            confidence=float(f.get("confidence", 0.5)),
        ))

    # Volume signals
    for vs in data.get("volume_signals", []):
        geometry.volume_signals.append(VolumeSignal(
            signal_type=vs.get("type", "unknown"),
            implication=_parse_implication(vs.get("implication", "neutral")),
            description=vs.get("location", ""),
        ))

    # Regime
    regime_data = data.get("regime", {})
    regime_map = {
        "trending_up": RegimeType.TRENDING_UP, "trending_down": RegimeType.TRENDING_DOWN,
        "trending": RegimeType.TRENDING_UP, "ranging": RegimeType.RANGING,
        "volatile": RegimeType.VOLATILE, "quiet": RegimeType.QUIET,
        "transitioning": RegimeType.TRANSITIONING,
    }
    geometry.regime = RegimeState(
        regime=regime_map.get(regime_data.get("state", "ranging"), RegimeType.RANGING),
        trend_strength=float(regime_data.get("trend_strength", 0)),
        volatility_percentile=0.5,
    )

    geometry.overall_bias = _parse_implication(data.get("overall_bias", "neutral"))
    geometry.confidence = float(data.get("confidence", 0.5))
    geometry.narrative = data.get("narrative", "")
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
