import numpy as np
import pandas as pd

from finvl.evaluation.metrics import sharpe_ratio
from finvl.evaluation.portfolio import synchronized_portfolio
from finvl.evaluation.statistics import holm_adjust, moving_block_bootstrap_sharpe


def test_zero_variance_sharpe_is_undefined():
    assert np.isnan(sharpe_ratio(np.zeros(30)))


def test_portfolio_is_computed_from_synchronized_daily_pnl():
    dates = pd.date_range("2025-01-01", periods=40, freq="B")
    left = pd.Series(np.tile([0.01, -0.005], 20), index=dates)
    right = pd.Series(np.tile([-0.002, 0.008], 20), index=dates)
    audit, metrics = synchronized_portfolio({"A": left, "B": right})
    expected = 0.5 * left + 0.5 * right
    np.testing.assert_allclose(audit["portfolio_return"], expected)
    assert metrics["n_assets"] == 2
    assert not np.isclose(metrics["sharpe_ratio"], (sharpe_ratio(left) + sharpe_ratio(right)) / 2)


def test_bootstrap_is_reproducible_and_holm_is_monotone():
    returns = np.sin(np.arange(120)) / 100 + 0.001
    a = moving_block_bootstrap_sharpe(returns, samples=100, block_size=10, seed=7)
    b = moving_block_bootstrap_sharpe(returns, samples=100, block_size=10, seed=7)
    assert a == b
    adjusted = holm_adjust({"a": 0.01, "b": 0.03, "c": 0.2})
    assert adjusted["a"] <= adjusted["b"] <= adjusted["c"]
