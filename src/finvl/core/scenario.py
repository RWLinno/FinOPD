"""
Scenario specification for FinVL-MAS experiments.
Adapted from R&D-Agent Scenario ABC for financial visual reasoning.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TemporalSplit:
    """Train/valid/test temporal split specification."""
    train_start: str = "2008-01-01"
    train_end: str = "2014-12-31"
    valid_start: str = "2015-01-01"
    valid_end: str = "2016-12-31"
    test_start: str = "2017-01-01"
    test_end: str = "2020-12-31"


@dataclass
class FinVLScenario:
    """
    Defines a complete experimental scenario for FinVL-MAS.
    Inspired by R&D-Agent(Q) Scenario abstraction.
    """
    name: str = "csi300_daily"
    market: str = "CSI300"
    asset_universe: List[str] = field(default_factory=lambda: ["000300.SH"])
    frequency: str = "daily"
    lookback_window: int = 60
    chart_types: List[str] = field(default_factory=lambda: ["candlestick_volume"])
    decision_type: str = "long_short_hold"

    temporal_split: TemporalSplit = field(default_factory=TemporalSplit)

    transaction_cost_bps: float = 15.0
    slippage_bps: float = 5.0
    execution_delay_days: int = 1

    metrics: List[str] = field(
        default_factory=lambda: [
            "sharpe_ratio",
            "annualized_return",
            "max_drawdown",
            "information_coefficient",
            "directional_accuracy",
        ]
    )

    constraints: Dict[str, Any] = field(default_factory=dict)

    @property
    def background(self) -> str:
        return (
            f"Financial visual reasoning scenario on {self.market} ({self.frequency}). "
            f"Lookback={self.lookback_window} bars, charts={self.chart_types}, "
            f"decision={self.decision_type}. "
            f"TC={self.transaction_cost_bps}bps, slippage={self.slippage_bps}bps."
        )

    def description(self) -> str:
        return (
            f"Scenario: {self.name}\n"
            f"  Market: {self.market}\n"
            f"  Assets: {self.asset_universe}\n"
            f"  Frequency: {self.frequency}\n"
            f"  Lookback: {self.lookback_window}\n"
            f"  Charts: {self.chart_types}\n"
            f"  Decision: {self.decision_type}\n"
            f"  Train: {self.temporal_split.train_start} to {self.temporal_split.train_end}\n"
            f"  Valid: {self.temporal_split.valid_start} to {self.temporal_split.valid_end}\n"
            f"  Test:  {self.temporal_split.test_start} to {self.temporal_split.test_end}\n"
            f"  TC: {self.transaction_cost_bps}bps, Slippage: {self.slippage_bps}bps\n"
            f"  Metrics: {self.metrics}\n"
        )

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "FinVLScenario":
        split_data = d.pop("temporal_split", {})
        split = TemporalSplit(**split_data) if split_data else TemporalSplit()
        return cls(temporal_split=split, **d)
