"""
AgentOrchestrator: Coordinates the multi-agent pipeline.
Runs agents sequentially, manages shared memory, collects outputs.
Ablation-aware: disabled agents inject neutral/empty values so that
downstream agents observe a meaningful change in information flow.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from finvl.agents.base import AgentOutput, BaseFinAgent
from finvl.agents.chart_analyst import ChartAnalystAgent
from finvl.agents.decision_pm import DecisionPMAgent
from finvl.agents.event_analyst import EventAnalystAgent
from finvl.agents.pattern_reasoner import PatternReasonerAgent
from finvl.agents.risk_controller import RiskControllerAgent
from finvl.core.memory import SharedMemory
from finvl.core.types import ChartGeometry, DecisionOutput, Implication

logger = logging.getLogger(__name__)

# Default neutral values that disabled agents write to memory so that
# downstream agents see explicit signals rather than relying on fallback
# defaults which would mask the effect of removing a component.
_DISABLED_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "ChartAnalyst": {
        "chart_geometry": ChartGeometry(
            overall_bias=Implication.NEUTRAL, confidence=0.0,
            narrative="Visual analysis disabled",
        ),
        "chart_narrative": "Visual analysis disabled",
        "chart_bias": "neutral",
    },
    "PatternReasoner": {
        "pattern_bias": "neutral",
        "pattern_assessments": [],
        "pattern_confidence": 0.0,
    },
    "EventAnalyst": {
        "event_bias": "neutral",
        "event_impact": 0.0,
    },
    "RiskController": {
        "risk_level": "moderate",
        "risk_assessment": {"recommendation": "proceed", "risk_factors": []},
        "position_size_pct": 0.05,
    },
}


class AgentOrchestrator:
    """
    Orchestrates the 5-agent reasoning pipeline:
    ChartAnalyst -> PatternReasoner -> EventAnalyst -> RiskController -> DecisionPM

    Manages SharedMemory with confidence-weighted writes and disagreement detection.
    Disabled agents inject neutral values so ablation experiments produce
    meaningfully different behaviour.
    """

    def __init__(self, config: Dict[str, Any] | None = None):
        config = config or {}
        agents_cfg = config.get("agents", {})

        self._agent_configs: Dict[str, Dict[str, Any]] = {
            "ChartAnalyst": agents_cfg.get("chart_analyst", {}),
            "PatternReasoner": agents_cfg.get("pattern_reasoner", {}),
            "EventAnalyst": agents_cfg.get("event_analyst", {}),
            "RiskController": agents_cfg.get("risk_controller", {}),
            "DecisionPM": agents_cfg.get("decision_pm", {}),
        }

        self.agents: List[BaseFinAgent] = []
        self._disabled_agents: List[str] = []

        for name, acfg in [
            ("ChartAnalyst", ChartAnalystAgent),
            ("PatternReasoner", PatternReasonerAgent),
            ("EventAnalyst", EventAnalystAgent),
            ("RiskController", RiskControllerAgent),
            ("DecisionPM", DecisionPMAgent),
        ]:
            cfg = self._agent_configs[name]
            if cfg.get("enabled", True):
                self.agents.append(acfg(cfg))
            else:
                self._disabled_agents.append(name)

        self.memory = SharedMemory()
        self.agent_outputs: List[AgentOutput] = []

    async def run(self, inputs: Dict[str, Any]) -> DecisionOutput:
        """
        Run the full agent pipeline on a single decision point.

        Args:
            inputs: Must include at minimum "ohlcv_df".
                    Optional: "chart_image_path", "vlm_client", "events", etc.

        Returns:
            DecisionOutput from the final DecisionPM agent.
        """
        self.memory.clear()
        self.agent_outputs.clear()

        # Write neutral defaults for disabled agents so downstream
        # agents observe the absence explicitly.
        for name in self._disabled_agents:
            defaults = _DISABLED_DEFAULTS.get(name, {})
            for key, value in defaults.items():
                self.memory.write(
                    key=key, value=value, confidence=0.0, source=f"{name}(disabled)",
                )
            self.memory.advance_step()

        for agent in self.agents:
            try:
                mem_dict = self.memory.as_dict()
                output = await agent.process(inputs, mem_dict)
                self.agent_outputs.append(output)

                writes = agent.flush_memory_writes()
                for entry in writes:
                    self.memory.write(
                        key=entry.key,
                        value=entry.value,
                        confidence=entry.confidence,
                        source=agent.name,
                    )
                self.memory.advance_step()

                logger.info(
                    f"[{agent.name}] success={output.success}, "
                    f"conf={output.confidence:.2f}"
                )
            except Exception as e:
                logger.error(f"[{agent.name}] failed: {e}")
                self.agent_outputs.append(AgentOutput(
                    agent_name=agent.name, success=False,
                    result={"error": str(e)}, confidence=0.0,
                ))

        # Detect disagreements and log them
        disagreements = self.memory.detect_disagreements()
        if disagreements:
            logger.info(f"Disagreements detected: {disagreements}")

        # Extract final decision from memory
        decision = self.memory.read("decision")
        if isinstance(decision, DecisionOutput):
            return decision

        return DecisionOutput(rationale="Pipeline completed but no structured decision produced")

    def get_reasoning_trace(self) -> str:
        lines = []
        for name in self._disabled_agents:
            lines.append(f"[{name}] (DISABLED)")
        for output in self.agent_outputs:
            status = "OK" if output.success else "FAIL"
            lines.append(
                f"[{output.agent_name}] ({status}, conf={output.confidence:.2f}): "
                f"{output.reasoning_trace or 'no trace'}"
            )
        return "\n".join(lines)

    def get_memory_snapshot(self) -> Dict[str, Any]:
        return {k: self.memory.read(k) for k in self.memory.keys}

    def get_disagreements(self) -> List[str]:
        return self.memory.detect_disagreements()

    @property
    def last_factor_ids(self) -> List[int]:
        for agent in self.agents:
            if isinstance(agent, DecisionPMAgent):
                return list(agent._last_factor_ids)
        return []

    @property
    def last_router_features(self) -> List[float]:
        for agent in self.agents:
            if isinstance(agent, DecisionPMAgent):
                return list(agent._last_router_features)
        return []

    @property
    def last_router_regime(self) -> List[float]:
        for agent in self.agents:
            if isinstance(agent, DecisionPMAgent):
                return list(agent._last_router_regime)
        return []

    @property
    def last_router_selected_indices(self) -> List[int]:
        for agent in self.agents:
            if isinstance(agent, DecisionPMAgent):
                return list(agent._last_router_selected_indices)
        return []

    @property
    def factor_router(self):
        for agent in self.agents:
            if isinstance(agent, DecisionPMAgent):
                agent._get_factor_lib()
                return agent._router
        return None

    @property
    def router_factor_names(self) -> List[str]:
        for agent in self.agents:
            if isinstance(agent, DecisionPMAgent):
                agent._get_factor_lib()
                return list(agent._router_factor_names)
        return []
