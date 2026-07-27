import numpy as np
import pytest

from finvl.self_evolution.credit.shapley import ShapleyCredit
from finvl.self_evolution.opsd.utility import outcome_utility


def test_outcome_utility_uses_realized_return_and_penalties():
    clean = outcome_utility(np.array([0.01, 0.005, -0.002]), turnover=0.1)
    costly = outcome_utility(np.array([0.01, 0.005, -0.002]), turnover=0.5)
    assert clean["utility"] > costly["utility"]
    assert clean["cumulative_return"] == pytest.approx(1.01 * 1.005 * 0.998 - 1)


def test_shapley_requires_replay_and_is_deterministic():
    with pytest.raises(RuntimeError):
        ShapleyCredit().estimate(object())

    contributions = {"ChartAnalyst": 2.0, "PatternReasoner": 1.0}

    def value(_trajectory, coalition):
        return sum(contributions.get(agent, 0.0) for agent in coalition)

    credit = ShapleyCredit(
        num_samples=16,
        agents=list(contributions),
        coalition_value=value,
        seed=7,
    ).estimate(object())
    assert credit["ChartAnalyst"] == pytest.approx(2 / 3)
    assert credit["PatternReasoner"] == pytest.approx(1 / 3)
