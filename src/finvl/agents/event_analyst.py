"""
EventAnalystAgent: Integrates non-visual context (news, fundamentals, macro).
Operates as a stub in MVP; provides neutral assessment when no event data is available.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from finvl.agents.base import AgentOutput, BaseFinAgent

logger = logging.getLogger(__name__)


class EventAnalystAgent(BaseFinAgent):
    """
    Integrates event, fundamental, and macro context.
    In MVP mode (stub=True), produces a neutral assessment.
    """

    def __init__(self, config: Dict[str, Any] | None = None):
        super().__init__("EventAnalyst", config or {})
        self.stub = (config or {}).get("stub", True)

    async def process(self, inputs: Dict[str, Any], memory: Dict[str, Any]) -> AgentOutput:
        if self.stub:
            return self._stub_response(inputs)

        events: List[Dict[str, Any]] = inputs.get("events", [])
        fundamentals = inputs.get("fundamentals", {})

        if not events and not fundamentals:
            return self._stub_response(inputs)

        # Score events by sentiment and relevance
        total_sentiment = 0.0
        total_weight = 0.0
        event_summaries = []

        for ev in events:
            sentiment = float(ev.get("sentiment", 0.0))
            relevance = float(ev.get("relevance", 0.5))
            total_sentiment += sentiment * relevance
            total_weight += relevance
            event_summaries.append(
                f"{ev.get('event_type', 'event')}: {ev.get('headline', '?')} "
                f"(sentiment={sentiment:.2f})"
            )

        if total_weight > 0:
            avg_sentiment = total_sentiment / total_weight
        else:
            avg_sentiment = 0.0

        if avg_sentiment > 0.2:
            bias = "bullish"
        elif avg_sentiment < -0.2:
            bias = "bearish"
        else:
            bias = "neutral"

        confidence = min(abs(avg_sentiment) + 0.3, 0.8)

        self.write_to_memory("event_bias", bias, confidence=confidence)
        self.write_to_memory("event_impact", avg_sentiment, confidence=confidence)
        self.write_to_memory("event_summaries", event_summaries, confidence=confidence)

        return AgentOutput(
            agent_name=self.name,
            success=True,
            result={
                "event_bias": bias,
                "event_impact": avg_sentiment,
                "event_count": len(events),
                "event_summaries": event_summaries,
            },
            confidence=confidence,
            reasoning_trace=f"Analyzed {len(events)} events, avg sentiment={avg_sentiment:.2f}",
        )

    def _stub_response(self, inputs: Dict[str, Any]) -> AgentOutput:
        self.write_to_memory("event_bias", "neutral", confidence=0.1)
        self.write_to_memory("event_impact", 0.0, confidence=0.1)
        return AgentOutput(
            agent_name=self.name,
            success=True,
            result={"event_bias": "neutral", "event_impact": 0.0, "stub": True},
            confidence=0.1,
            reasoning_trace="No event data available (stub mode); neutral assessment.",
        )
