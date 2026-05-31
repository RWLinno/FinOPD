"""
Belief Extractor: extracts (geometry_signature, factor_set, action_pattern, realized_J)
quadruples from high-score trajectories for the belief store.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class BeliefEntry:
    """A single belief store entry (quadruple)."""
    geometry_signature: np.ndarray  # mean-pooled VLM geometry token embedding
    factor_set: List[int]  # selected factor IDs
    action_pattern: str  # e.g., "buy_high_confidence"
    realized_j: float  # realized performance score
    asset: str = ""
    date: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class BeliefExtractor:
    """
    Extracts belief entries from high-score trajectories.
    Only trajectories above the admission percentile are stored.
    """

    def __init__(self, embedding_dim: int = 768, admission_percentile: int = 80):
        self.embedding_dim = embedding_dim
        self.admission_percentile = admission_percentile

    def extract_from_trajectories(self, trajectories: List) -> List[BeliefEntry]:
        """Extract belief entries from a list of high-score trajectories."""
        beliefs = []

        for traj in trajectories:
            if not traj.steps:
                continue

            geometry_sig = self._compute_geometry_signature(traj)

            factor_set = list(range(15))

            action_counts = {}
            for step in traj.steps:
                action = step.action
                action_counts[action] = action_counts.get(action, 0) + 1
            dominant_action = max(action_counts, key=action_counts.get) if action_counts else "hold"
            avg_confidence = np.mean([s.confidence for s in traj.steps])
            action_pattern = f"{dominant_action}_{'high' if avg_confidence > 0.7 else 'low'}_confidence"

            entry = BeliefEntry(
                geometry_signature=geometry_sig,
                factor_set=factor_set,
                action_pattern=action_pattern,
                realized_j=traj.score,
                asset=traj.asset,
                date=traj.steps[-1].date if traj.steps else "",
            )
            beliefs.append(entry)

        logger.info(f"Extracted {len(beliefs)} belief entries")
        return beliefs

    def _compute_geometry_signature(self, trajectory) -> np.ndarray:
        """
        Compute geometry signature as mean-pooled embedding.
        In production, this would use VLM last-layer geometry tokens.
        """
        return np.random.randn(self.embedding_dim).astype(np.float32)
