import numpy as np

from finvl.self_evolution.belief.extractor import BeliefEntry
from finvl.self_evolution.belief.index import BeliefIndex


def test_belief_retrieval_filters_unavailable_outcomes_and_counts_queries():
    index = BeliefIndex(capacity=10, embedding_dim=4)
    index.add_beliefs(
        [
            BeliefEntry(
                geometry_signature=np.array([1.0, 0.0, 0.0, 0.0]),
                factor_set=[1],
                action_pattern="buy_high_confidence",
                realized_j=1.0,
                available_date="2021-01-10",
            ),
            BeliefEntry(
                geometry_signature=np.array([0.9, 0.1, 0.0, 0.0]),
                factor_set=[2],
                action_pattern="sell_high_confidence",
                realized_j=2.0,
                available_date="2021-02-10",
            ),
        ]
    )

    early = index.query(np.array([1.0, 0.0]), top_k=5, as_of_date="2021-01-20")
    assert len(early) == 1
    assert early[0][0]["factor_set"] == [1]
    assert index.hit_rate == 1.0

    unavailable = index.query(
        np.array([1.0, 0.0]), top_k=5, as_of_date="2020-12-31"
    )
    assert unavailable == []
    assert index.hit_rate == 0.5
