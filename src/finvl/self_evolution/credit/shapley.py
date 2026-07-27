"""
Shapley Credit Assignment.
Estimates each agent's marginal contribution to trajectory performance
via leave-subset-out replay with random agent subsets.
"""
from __future__ import annotations

import logging
from typing import Callable, Dict, FrozenSet, List

import numpy as np

logger = logging.getLogger(__name__)

AGENT_NAMES = ["ChartAnalyst", "PatternReasoner", "EventAnalyst", "RiskController", "DecisionPM"]


class ShapleyCredit:
    """
    Approximate Shapley value estimation for multi-agent credit assignment.
    For each high-score trajectory, randomly samples m agent subsets
    and estimates marginal contributions via leave-subset-out replay.
    """

    def __init__(
        self,
        num_samples: int = 8,
        agents: List[str] = None,
        coalition_value: Callable[[object, FrozenSet[str]], float] | None = None,
        seed: int = 42,
    ):
        self.num_samples = num_samples
        self.agents = agents or AGENT_NAMES
        self.coalition_value = coalition_value
        self.rng = np.random.default_rng(seed)

    def estimate(self, trajectory) -> Dict[str, float]:
        """
        Estimate Shapley values for each agent in a trajectory.
        
        Uses Monte Carlo approximation:
        For each sample, draw a random permutation, compute marginal
        contribution of each agent by comparing performance with/without.
        """
        n_agents = len(self.agents)
        marginals = {agent: [] for agent in self.agents}

        if self.coalition_value is None:
            raise RuntimeError(
                "Shapley credit requires a deterministic coalition evaluator; "
                "heuristic/noisy replay is not permitted."
            )

        for _ in range(self.num_samples):
            perm = self.rng.permutation(n_agents)
            coalition: set[str] = set()
            prev_score = self.coalition_value(trajectory, frozenset())

            for idx in perm:
                agent = self.agents[idx]
                coalition.add(agent)
                current_score = self.coalition_value(trajectory, frozenset(coalition))
                marginal = current_score - prev_score
                marginals[agent].append(marginal)
                prev_score = current_score

        shapley_values = {}
        for agent in self.agents:
            vals = marginals[agent]
            shapley_values[agent] = float(np.mean(vals)) if vals else 0.0

        total = sum(abs(v) for v in shapley_values.values())
        if total > 0:
            shapley_values = {k: v / total for k, v in shapley_values.items()}

        return shapley_values

    def compute_distillation_weights(
        self, shapley_values: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Convert Shapley values to per-agent distillation sample weights.
        Higher contribution -> higher weight in distillation loss.
        """
        min_weight = 0.1
        weights = {}
        for agent, value in shapley_values.items():
            weights[agent] = max(min_weight, value)

        total = sum(weights.values())
        return {k: v / total for k, v in weights.items()}
