"""
PatternReasonerAgent: Interprets chart geometry in historical context,
matches formations to known patterns, provides directional hypothesis.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from finvl.agents.base import AgentOutput, BaseFinAgent
from finvl.core.types import ChartGeometry, Implication

logger = logging.getLogger(__name__)

# Historical base rates for common chart patterns (from technical analysis literature)
PATTERN_BASE_RATES: Dict[str, Dict[str, float]] = {
    "double_top": {"bearish_pct": 0.65, "avg_move_pct": -5.0},
    "double_bottom": {"bullish_pct": 0.65, "avg_move_pct": 5.0},
    "head_and_shoulders": {"bearish_pct": 0.70, "avg_move_pct": -7.0},
    "head-and-shoulders": {"bearish_pct": 0.70, "avg_move_pct": -7.0},
    "ascending_triangle": {"bullish_pct": 0.68, "avg_move_pct": 4.5},
    "descending_triangle": {"bearish_pct": 0.68, "avg_move_pct": -4.5},
    "symmetrical_triangle": {"breakout_either": 0.50, "avg_move_pct": 3.0},
    "engulfing_bullish": {"bullish_pct": 0.60, "avg_move_pct": 2.0},
    "bullish_engulfing": {"bullish_pct": 0.60, "avg_move_pct": 2.0},
    "bullish engulfing": {"bullish_pct": 0.60, "avg_move_pct": 2.0},
    "engulfing_bearish": {"bearish_pct": 0.60, "avg_move_pct": -2.0},
    "bearish_engulfing": {"bearish_pct": 0.60, "avg_move_pct": -2.0},
    "bearish engulfing": {"bearish_pct": 0.60, "avg_move_pct": -2.0},
    "morning_star": {"bullish_pct": 0.65, "avg_move_pct": 3.0},
    "morning star": {"bullish_pct": 0.65, "avg_move_pct": 3.0},
    "evening_star": {"bearish_pct": 0.65, "avg_move_pct": -3.0},
    "evening star": {"bearish_pct": 0.65, "avg_move_pct": -3.0},
    "hammer": {"bullish_pct": 0.58, "avg_move_pct": 1.5},
    "inverted_hammer": {"bullish_pct": 0.55, "avg_move_pct": 1.0},
    "inverted hammer": {"bullish_pct": 0.55, "avg_move_pct": 1.0},
    "shooting_star": {"bearish_pct": 0.58, "avg_move_pct": -1.5},
    "shooting star": {"bearish_pct": 0.58, "avg_move_pct": -1.5},
    "three_white_soldiers": {"bullish_pct": 0.70, "avg_move_pct": 4.0},
    "three_black_crows": {"bearish_pct": 0.70, "avg_move_pct": -4.0},
    "doji": {"bullish_pct": 0.50, "bearish_pct": 0.50, "avg_move_pct": 0.0},
    "spinning_top": {"bullish_pct": 0.50, "bearish_pct": 0.50, "avg_move_pct": 0.0},
    "marubozu": {"bullish_pct": 0.62, "avg_move_pct": 2.5},
}


def _normalize_pattern_name(name: str) -> str:
    """Normalize pattern name for lookup."""
    n = name.lower().strip()
    # Try direct lookup first, then underscore variant
    if n in PATTERN_BASE_RATES:
        return n
    n_under = n.replace(" ", "_").replace("-", "_")
    if n_under in PATTERN_BASE_RATES:
        return n_under
    # Partial match
    for key in PATTERN_BASE_RATES:
        if key in n or n in key:
            return key
    return n


class PatternReasonerAgent(BaseFinAgent):
    """
    Interprets detected chart patterns using historical base rates
    and contextual signals to form a directional hypothesis.
    """

    def __init__(self, config: Dict[str, Any] | None = None):
        super().__init__("PatternReasoner", config or {})

    async def process(self, inputs: Dict[str, Any], memory: Dict[str, Any]) -> AgentOutput:
        geometry: ChartGeometry | None = memory.get("chart_geometry")
        if geometry is None:
            return AgentOutput(
                agent_name=self.name, success=False,
                result={}, confidence=0.0,
                reasoning_trace="No chart geometry available in memory",
            )

        assessments = []
        bias_score = 0.0
        total_weight = 0.0

        # Assess formations
        for f in geometry.formations:
            norm_name = _normalize_pattern_name(f.formation_type)
            rates = PATTERN_BASE_RATES.get(norm_name, {})
            if rates:
                bull = rates.get("bullish_pct", 0)
                bear = rates.get("bearish_pct", 0)
                avg_move = rates.get("avg_move_pct", 0)
                direction = "bullish" if bull > bear else "bearish"
                success_rate = max(bull, bear)
                weight = f.confidence * success_rate
                bias_score += weight * (1.0 if direction == "bullish" else -1.0)
                total_weight += weight

                assessments.append({
                    "pattern": f.formation_type,
                    "quality": "textbook" if f.confidence > 0.7 else "acceptable",
                    "historical_success_rate": success_rate,
                    "directional_implication": direction,
                    "expected_move_pct": avg_move,
                    "confidence": f.confidence,
                    "stage": f.stage.value,
                })

        # Assess candlestick patterns
        for cp in geometry.candlestick_patterns:
            norm_name = _normalize_pattern_name(cp.pattern)
            rates = PATTERN_BASE_RATES.get(norm_name, {})
            if rates:
                bull = rates.get("bullish_pct", 0)
                bear = rates.get("bearish_pct", 0)
                direction = "bullish" if cp.implication == Implication.BULLISH else "bearish"
                success_rate = max(bull, bear) if rates else 0.55
                weight = 0.3 * success_rate
                bias_score += weight * (1.0 if direction == "bullish" else -1.0)
                total_weight += weight

                assessments.append({
                    "pattern": cp.pattern,
                    "quality": "acceptable",
                    "historical_success_rate": success_rate,
                    "directional_implication": direction,
                    "confidence": 0.5,
                })

        if total_weight > 0:
            normalized_bias = bias_score / total_weight
        else:
            normalized_bias = 0.0

        if normalized_bias > 0.2:
            overall_bias = "bullish"
        elif normalized_bias < -0.2:
            overall_bias = "bearish"
        else:
            overall_bias = "neutral"

        # Build confirming/contradicting signals
        confirming = [a["pattern"] for a in assessments
                      if a["directional_implication"] == overall_bias]
        contradicting = [a["pattern"] for a in assessments
                         if a["directional_implication"] != overall_bias
                         and a["directional_implication"] != "neutral"]

        confidence = min(abs(normalized_bias) + 0.3, 0.95) if assessments else 0.2
        reasoning = (
            f"Analyzed {len(assessments)} patterns. "
            f"Bias score: {normalized_bias:.2f} ({overall_bias}). "
            f"Confirming: {confirming}. Contradicting: {contradicting}."
        )

        self.write_to_memory("pattern_bias", overall_bias, confidence=confidence)
        self.write_to_memory("pattern_assessments", assessments, confidence=confidence)
        self.write_to_memory("pattern_confidence", confidence, confidence=confidence)

        return AgentOutput(
            agent_name=self.name,
            success=True,
            result={
                "pattern_assessments": assessments,
                "overall_pattern_bias": overall_bias,
                "confirming_signals": confirming,
                "contradicting_signals": contradicting,
                "bias_score": normalized_bias,
            },
            confidence=confidence,
            reasoning_trace=reasoning,
        )
