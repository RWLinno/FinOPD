"""
AgentOrchestrator: Coordinates the multi-agent pipeline.
Runs agents sequentially, manages shared memory, collects outputs.
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
from finvl.core.types import DecisionOutput

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """
    Orchestrates the 5-agent reasoning pipeline:
    ChartAnalyst -> PatternReasoner -> EventAnalyst -> RiskController -> DecisionPM

    Manages SharedMemory with confidence-weighted writes and disagreement detection.
    """

    def __init__(self, config: Dict[str, Any] | None = None):
        config = config or {}
        agents_cfg = config.get("agents", {})

        self.agents: List[BaseFinAgent] = [
            ChartAnalystAgent(agents_cfg.get("chart_analyst", {})),
            PatternReasonerAgent(agents_cfg.get("pattern_reasoner", {})),
            EventAnalystAgent(agents_cfg.get("event_analyst", {})),
            RiskControllerAgent(agents_cfg.get("risk_controller", {})),
            DecisionPMAgent(agents_cfg.get("decision_pm", {})),
        ]

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

        for agent in self.agents:
            try:
                mem_dict = self.memory.as_dict()
                output = await agent.process(inputs, mem_dict)
                self.agent_outputs.append(output)

                # Apply memory writes via structured SharedMemory
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
