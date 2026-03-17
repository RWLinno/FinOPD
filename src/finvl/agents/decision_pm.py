"""
DecisionPMAgent: Final portfolio manager that integrates all agent outputs
and produces a DecisionOutput (buy/sell/hold with rationale).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from finvl.agents.base import AgentOutput, BaseFinAgent
from finvl.core.types import Action, Conviction, DecisionOutput, Implication

logger = logging.getLogger(__name__)


class DecisionPMAgent(BaseFinAgent):
    """
    Integrates evidence from all prior agents via shared memory
    and produces a final trading decision with rationale.
    """

    def __init__(self, config: Dict[str, Any] | None = None):
        super().__init__("DecisionPM", config or {})
        self.integration_mode = (config or {}).get("integration_mode", "confidence_weighted")

    async def process(self, inputs: Dict[str, Any], memory: Dict[str, Any]) -> AgentOutput:
        chart_bias = memory.get("chart_bias", "neutral")
        chart_confidence = memory.get("_confidence_chart_bias", 0.5)

        pattern_bias = memory.get("pattern_bias", "neutral")
        pattern_confidence = memory.get("_confidence_pattern_bias", 0.5)

        event_bias = memory.get("event_bias", "neutral")
        event_confidence = memory.get("_confidence_event_bias", 0.1)

        risk_level = memory.get("risk_level", "moderate")
        risk_confidence = memory.get("_confidence_risk_level", 0.5)
        risk_assessment = memory.get("risk_assessment", {})
        position_pct = memory.get("position_size_pct", 0.05)

        # Score biases: bullish=+1, bearish=-1, neutral=0
        bias_map = {"bullish": 1.0, "bearish": -1.0, "neutral": 0.0}
        signals = [
            ("chart", bias_map.get(chart_bias, 0.0), chart_confidence),
            ("pattern", bias_map.get(pattern_bias, 0.0), pattern_confidence),
            ("event", bias_map.get(event_bias, 0.0), event_confidence),
        ]

        # Confidence-weighted score
        weighted_score = 0.0
        total_conf = 0.0
        for name, score, conf in signals:
            weighted_score += score * conf
            total_conf += conf

        if total_conf > 0:
            normalized_score = weighted_score / total_conf
        else:
            normalized_score = 0.0

        # Apply risk filter
        risk_mult = {"low": 1.0, "moderate": 0.8, "high": 0.5, "extreme": 0.2}
        risk_factor = risk_mult.get(risk_level, 0.5)
        adjusted_score = normalized_score * risk_factor

        # Determine action
        if adjusted_score > 0.2:
            action = Action.BUY
        elif adjusted_score < -0.2:
            action = Action.SELL
        else:
            action = Action.HOLD

        # Risk recommendation override
        recommendation = risk_assessment.get("recommendation", "proceed")
        if recommendation == "avoid":
            action = Action.HOLD
            adjusted_score = 0.0

        # Conviction
        abs_score = abs(adjusted_score)
        if abs_score > 0.6:
            conviction = Conviction.HIGH
        elif abs_score > 0.3:
            conviction = Conviction.MODERATE
        else:
            conviction = Conviction.LOW

        # Detect contradictions
        disagreements = self._detect_disagreements(signals)

        # Build rationale
        rationale_parts = [
            f"Chart analysis ({chart_bias}, conf={chart_confidence:.2f})",
            f"Pattern analysis ({pattern_bias}, conf={pattern_confidence:.2f})",
            f"Event context ({event_bias}, conf={event_confidence:.2f})",
            f"Risk level: {risk_level} (rec={recommendation})",
            f"Weighted score: {normalized_score:.3f}, risk-adjusted: {adjusted_score:.3f}",
        ]
        if disagreements:
            rationale_parts.append(f"Disagreements: {'; '.join(disagreements)}")
        rationale = " | ".join(rationale_parts)

        confidence = min(abs_score + 0.2, 0.95)

        decision = DecisionOutput(
            action=action,
            conviction=conviction,
            position_size_pct=float(position_pct) if action != Action.HOLD else 0.0,
            stop_loss=risk_assessment.get("stop_loss"),
            take_profit=risk_assessment.get("take_profit"),
            confidence=confidence,
            rationale=rationale,
            key_evidence=[f"{name}: {score:+.2f}" for name, score, _ in signals],
            risks_acknowledged=risk_assessment.get("risk_factors", []),
            contradictions_resolved="; ".join(disagreements) if disagreements else "None",
            agent_confidences={
                "chart": chart_confidence,
                "pattern": pattern_confidence,
                "event": event_confidence,
                "risk": risk_confidence,
            },
        )

        self.write_to_memory("decision", decision, confidence=confidence)

        return AgentOutput(
            agent_name=self.name,
            success=True,
            result={
                "action": action.value,
                "conviction": conviction.value,
                "confidence": confidence,
                "position_pct": decision.position_size_pct,
                "weighted_score": adjusted_score,
            },
            confidence=confidence,
            reasoning_trace=rationale,
        )

    def _detect_disagreements(
        self, signals: List[tuple[str, float, float]]
    ) -> List[str]:
        disagreements = []
        for i, (n1, s1, c1) in enumerate(signals):
            for n2, s2, c2 in signals[i + 1:]:
                if s1 * s2 < 0 and min(c1, c2) > 0.3:
                    dir1 = "bullish" if s1 > 0 else "bearish"
                    dir2 = "bullish" if s2 > 0 else "bearish"
                    disagreements.append(f"{n1}({dir1}) vs {n2}({dir2})")
        return disagreements
