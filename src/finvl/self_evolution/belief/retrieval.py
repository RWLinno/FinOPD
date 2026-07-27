"""
Belief Retrieval: inference-time retrieval of relevant beliefs
from the belief store to inject as few-shot priors.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

import numpy as np

from finvl.self_evolution.belief.index import BeliefIndex

logger = logging.getLogger(__name__)


class BeliefRetrieval:
    """
    At inference time, retrieves top-k nearest beliefs from the store
    and injects them as few-shot priors into shared memory.
    """

    def __init__(self, belief_index: BeliefIndex, top_k: int = 5):
        self.belief_index = belief_index
        self.top_k = top_k

    def retrieve(
        self, geometry_signature: np.ndarray, as_of_date: str | None = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant beliefs for current market state.
        Returns list of (factor_set, action_pattern) priors.
        """
        if self.belief_index.size == 0:
            return []

        results = self.belief_index.query(
            geometry_signature, self.top_k, as_of_date=as_of_date
        )

        priors = []
        for metadata, similarity in results:
            priors.append({
                "factor_set": metadata.get("factor_set", []),
                "action_pattern": metadata.get("action_pattern", ""),
                "realized_j": metadata.get("realized_j", 0.0),
                "similarity": similarity,
                "asset": metadata.get("asset", ""),
            })

        return priors

    def inject_into_memory(
        self,
        memory,
        geometry_signature: np.ndarray,
        as_of_date: str | None = None,
    ) -> int:
        """
        Inject retrieved beliefs into shared memory as few-shot priors.
        Returns number of beliefs injected.
        """
        priors = self.retrieve(geometry_signature, as_of_date=as_of_date)

        if not priors:
            return 0

        memory.write(
            key="belief_priors",
            value=priors,
            confidence=0.8,
            source="BeliefStore",
        )

        best_prior = max(priors, key=lambda p: p["realized_j"])
        memory.write(
            key="belief_suggested_factors",
            value=best_prior["factor_set"],
            confidence=best_prior["similarity"],
            source="BeliefStore",
        )
        memory.write(
            key="belief_suggested_action",
            value=best_prior["action_pattern"],
            confidence=best_prior["similarity"],
            source="BeliefStore",
        )

        return len(priors)
