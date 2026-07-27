"""Synchronized multi-asset portfolio evaluation.

Risk ratios must be computed from the portfolio's daily PnL, never by
averaging per-asset Sharpe or Calmar ratios.  This module makes the capital,
cash and rebalancing assumptions explicit and emits the daily audit trail.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import pandas as pd

from finvl.evaluation.metrics import compute_all_metrics


@dataclass(frozen=True)
class PortfolioConfig:
    initial_capital: float = 1_000_000.0
    rebalance: str = "daily"
    cash_return_annual: float = 0.0
    periods_per_year: int = 252


def synchronized_portfolio(
    asset_returns: Mapping[str, pd.Series],
    weights: Mapping[str, float] | pd.DataFrame | None = None,
    config: PortfolioConfig = PortfolioConfig(),
) -> tuple[pd.DataFrame, dict[str, float]]:
    """Build one portfolio series on the intersection of asset timestamps.

    ``asset_returns`` must already include asset-level trading costs. Static
    weights are interpreted as fractions of initial capital; unused capital
    remains in cash. A DataFrame permits point-in-time dynamic weights.
    """
    if not asset_returns:
        raise ValueError("asset_returns cannot be empty")
    frame = pd.concat({k: v.astype(float) for k, v in asset_returns.items()}, axis=1, join="inner")
    frame = frame.sort_index()
    if frame.empty or frame.isna().any().any():
        raise ValueError("returns must share non-null synchronized timestamps")

    assets = list(frame.columns)
    if weights is None:
        weight_frame = pd.DataFrame(1.0 / len(assets), index=frame.index, columns=assets)
    elif isinstance(weights, pd.DataFrame):
        weight_frame = weights.reindex(index=frame.index, columns=assets).ffill()
        if weight_frame.isna().any().any():
            raise ValueError("dynamic weights do not cover the full return window")
    else:
        unknown = set(weights) - set(assets)
        if unknown:
            raise ValueError(f"weights contain unknown assets: {sorted(unknown)}")
        weight_frame = pd.DataFrame(
            {asset: float(weights.get(asset, 0.0)) for asset in assets}, index=frame.index
        )
    gross = weight_frame.abs().sum(axis=1)
    if (gross > 1.0 + 1e-12).any():
        raise ValueError("gross exposure exceeds 100%; leverage must be modeled explicitly")

    cash_weight = 1.0 - weight_frame.sum(axis=1)
    cash_daily = (1.0 + config.cash_return_annual) ** (1.0 / config.periods_per_year) - 1.0
    portfolio_return = (weight_frame * frame).sum(axis=1) + cash_weight * cash_daily
    equity = config.initial_capital * (1.0 + portfolio_return).cumprod()
    audit = frame.add_prefix("return_")
    for asset in assets:
        audit[f"weight_{asset}"] = weight_frame[asset]
    audit["cash_weight"] = cash_weight
    audit["portfolio_return"] = portfolio_return
    audit["equity"] = equity
    metrics = compute_all_metrics(portfolio_return.to_numpy())
    metrics.update({"n_assets": len(assets), "n_days": len(audit)})
    return audit, metrics
