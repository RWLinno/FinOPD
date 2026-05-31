"""
Vectorized backtester for FinVL-MAS.
Evaluates trading decisions under realistic conditions with
transaction costs, slippage, and execution delay.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from finvl.core.types import Action, DecisionOutput
from finvl.evaluation.metrics import compute_all_metrics

logger = logging.getLogger(__name__)


@dataclass
class BacktestConfig:
    transaction_cost_bps: float = 15.0
    slippage_bps: float = 5.0
    execution_delay_days: int = 1
    initial_capital: float = 1_000_000.0


@dataclass
class BacktestResult:
    """Complete backtest results."""
    metrics: Dict[str, float] = field(default_factory=dict)
    equity_curve: Optional[pd.Series] = None
    returns: Optional[np.ndarray] = None
    positions: Optional[pd.Series] = None
    decisions: List[Dict[str, Any]] = field(default_factory=list)
    config: Optional[BacktestConfig] = None


class VectorizedBacktester:
    """
    Runs a backtest given a sequence of (date, DecisionOutput) pairs
    and the corresponding OHLCV data.

    Handles:
    - Execution delay (decision on day T, executed at open of day T+delay)
    - Transaction costs (applied on each position change)
    - Slippage (added to transaction costs)
    """

    def __init__(self, config: BacktestConfig | None = None):
        self.config = config or BacktestConfig()

    def run(
        self,
        decisions: List[Dict[str, Any]],
        ohlcv_df: pd.DataFrame,
    ) -> BacktestResult:
        """
        Run backtest.

        Args:
            decisions: List of {"date": str, "decision": DecisionOutput} dicts.
            ohlcv_df: Full OHLCV DataFrame covering the backtest period.

        Returns:
            BacktestResult with metrics, equity curve, and per-trade details.
        """
        if not decisions or len(ohlcv_df) < 2:
            return BacktestResult()

        # Build decision lookup: date -> action signal (+1, -1, 0)
        decision_signals: Dict[str, float] = {}
        decision_sizes: Dict[str, float] = {}
        for d in decisions:
            if "date" not in d or "decision" not in d:
                logger.warning(f"Skipping malformed decision entry: {d}")
                continue
            date = d["date"]
            dec: DecisionOutput = d["decision"]
            if not isinstance(dec, DecisionOutput):
                logger.warning(f"Skipping non-DecisionOutput for {date}")
                continue
            signal = {Action.BUY: 1.0, Action.SELL: -1.0, Action.HOLD: 0.0}.get(dec.action, 0.0)
            decision_signals[date] = signal
            decision_sizes[date] = dec.position_size_pct

        dates = ohlcv_df.index
        close = ohlcv_df["close"].values
        n = len(close)

        # Map dates to positions with execution delay
        positions = np.zeros(n)
        current_pos = 0.0
        delay = self.config.execution_delay_days

        def _date_to_str(idx_val) -> str:
            if hasattr(idx_val, "strftime"):
                return idx_val.strftime("%Y-%m-%d")
            return str(idx_val)[:10]

        for i in range(n):
            if i >= delay:
                signal_date = _date_to_str(dates[i - delay])
                if signal_date in decision_signals:
                    sig = decision_signals[signal_date]
                    size = decision_sizes.get(signal_date, 0.05)
                    if sig != 0.0:
                        # BUY or SELL: update position
                        current_pos = sig * size
                    # HOLD (sig==0): keep current_pos unchanged
            positions[i] = current_pos

        # Compute returns
        price_returns = np.diff(close) / close[:-1]

        # Strategy returns (positions are applied to next-day returns)
        strategy_returns = np.zeros(n - 1)
        for i in range(n - 1):
            strategy_returns[i] = positions[i] * price_returns[i]

        # Apply transaction costs on position changes
        cost_rate = (self.config.transaction_cost_bps + self.config.slippage_bps) / 10000.0
        position_changes = np.abs(np.diff(np.concatenate([[0.0], positions])))
        costs = position_changes[:-1] * cost_rate

        net_returns = strategy_returns - costs

        # Equity curve (starting from initial capital)
        equity = self.config.initial_capital * np.cumprod(1 + net_returns)
        equity = np.concatenate([[self.config.initial_capital], equity])
        equity_series = pd.Series(equity, index=dates)

        # Prediction signals for IC calculation
        preds = np.array([positions[i] for i in range(n - 1)])
        actuals = price_returns

        metrics = compute_all_metrics(
            returns=net_returns,
            predictions=preds,
            actuals=actuals,
            pnl=net_returns,
        )

        # Add cost-free metrics for comparison
        metrics_no_cost = compute_all_metrics(returns=strategy_returns)
        metrics["sharpe_no_cost"] = metrics_no_cost["sharpe_ratio"]
        metrics["return_no_cost"] = metrics_no_cost["annualized_return"]

        return BacktestResult(
            metrics=metrics,
            equity_curve=equity_series,
            returns=net_returns,
            positions=pd.Series(positions, index=dates),
            decisions=decisions,
            config=self.config,
        )
