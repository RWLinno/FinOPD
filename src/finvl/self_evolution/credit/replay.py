"""Deterministic same-horizon coalition replay for agent credit."""
from __future__ import annotations

import copy
from typing import Dict, FrozenSet, Tuple

from finvl.self_evolution.opsd.rollout import StudentRollout, Trajectory
from finvl.workflow.orchestrator import AgentOrchestrator


AGENT_CONFIG_KEYS = {
    "ChartAnalyst": "chart_analyst",
    "PatternReasoner": "pattern_reasoner",
    "EventAnalyst": "event_analyst",
    "RiskController": "risk_controller",
    "DecisionPM": "decision_pm",
}


class CoalitionReplayEvaluator:
    """Replay a trajectory with exactly one supplied coalition enabled.

    ``policy_backend`` is optional. When present, it must expose
    ``wrap_orchestrator(orchestrator, decision_enabled=...)`` so coalition
    replays use the same deployable student as the original rollout.
    """

    def __init__(
        self,
        config,
        provider,
        rollout: StudentRollout,
        policy_backend=None,
        belief_index=None,
    ):
        self.config = config
        self.provider = provider
        self.rollout = rollout
        self.policy_backend = policy_backend
        self.belief_index = belief_index
        self._cache: Dict[Tuple[str, Tuple[str, ...], FrozenSet[str]], float] = {}

    def __call__(self, trajectory: Trajectory, coalition: FrozenSet[str]) -> float:
        dates = tuple(step.date for step in trajectory.steps)
        key = (trajectory.asset, dates, coalition)
        if key in self._cache:
            return self._cache[key]

        config = copy.deepcopy(self.config)
        agents = config.setdefault("agents", {})
        for agent_name, config_key in AGENT_CONFIG_KEYS.items():
            agents.setdefault(config_key, {})["enabled"] = agent_name in coalition

        orchestrator = AgentOrchestrator(config)
        if self.policy_backend is not None:
            orchestrator = self.policy_backend.wrap_orchestrator(
                orchestrator,
                decision_enabled="DecisionPM" in coalition,
            )

        replay = self.rollout.rollout_window(
            orchestrator,
            self.provider,
            list(dates),
            trajectory.asset,
            belief_index=self.belief_index,
        )
        if replay is None or replay.length != trajectory.length:
            raise RuntimeError(
                "coalition replay did not reproduce the original decision horizon"
            )
        self.rollout.compute_posthoc_metrics(replay, self.provider)
        self._cache[key] = replay.score
        return replay.score
