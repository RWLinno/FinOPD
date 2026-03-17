"""
Financial evaluation metrics for FinVL-MAS.
Computes Sharpe ratio, IC, max drawdown, and other standard quantitative metrics.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


def sharpe_ratio(
    returns: np.ndarray, risk_free_rate: float = 0.0, annualization: float = 252.0
) -> float:
    """Annualized Sharpe ratio."""
    excess = returns - risk_free_rate / annualization
    if len(excess) < 2 or np.std(excess) < 1e-12:
        return 0.0
    return float(np.mean(excess) / np.std(excess) * np.sqrt(annualization))


def annualized_return(returns: np.ndarray, periods_per_year: float = 252.0) -> float:
    """Annualized return from daily returns."""
    if len(returns) == 0:
        return 0.0
    cumulative = np.prod(1 + returns) - 1
    n_years = len(returns) / periods_per_year
    if n_years < 1e-6:
        return 0.0
    return float((1 + cumulative) ** (1.0 / n_years) - 1)


def max_drawdown(returns: np.ndarray) -> float:
    """Maximum drawdown from a return series."""
    if len(returns) == 0:
        return 0.0
    cumulative = np.cumprod(1 + returns)
    peak = np.maximum.accumulate(cumulative)
    drawdown = (peak - cumulative) / peak
    return float(np.max(drawdown))


def calmar_ratio(returns: np.ndarray, periods_per_year: float = 252.0) -> float:
    """Calmar ratio = annualized return / max drawdown."""
    ann_ret = annualized_return(returns, periods_per_year)
    mdd = max_drawdown(returns)
    if mdd < 1e-8:
        return 0.0
    return float(ann_ret / mdd)


def information_coefficient(predictions: np.ndarray, actuals: np.ndarray) -> float:
    """IC = Pearson correlation between predictions and actuals."""
    if len(predictions) < 2:
        return 0.0
    return float(np.corrcoef(predictions, actuals)[0, 1])


def rank_ic(predictions: np.ndarray, actuals: np.ndarray) -> float:
    """Rank IC = Spearman rank correlation."""
    if len(predictions) < 2:
        return 0.0
    from scipy.stats import spearmanr
    corr, _ = spearmanr(predictions, actuals)
    return float(corr) if not np.isnan(corr) else 0.0


def directional_accuracy(predictions: np.ndarray, actuals: np.ndarray) -> float:
    """Fraction of correct directional predictions."""
    if len(predictions) == 0:
        return 0.0
    correct = np.sign(predictions) == np.sign(actuals)
    return float(np.mean(correct))


def win_rate(pnl_series: np.ndarray) -> float:
    """Fraction of positive PnL trades."""
    if len(pnl_series) == 0:
        return 0.0
    return float(np.mean(pnl_series > 0))


def profit_factor(pnl_series: np.ndarray) -> float:
    """Sum of gains / sum of losses."""
    gains = pnl_series[pnl_series > 0].sum()
    losses = abs(pnl_series[pnl_series < 0].sum())
    if losses < 1e-12:
        return float("inf") if gains > 0 else 0.0
    return float(gains / losses)


def compute_all_metrics(
    returns: np.ndarray,
    predictions: Optional[np.ndarray] = None,
    actuals: Optional[np.ndarray] = None,
    pnl: Optional[np.ndarray] = None,
) -> Dict[str, float]:
    """Compute all standard financial metrics."""
    metrics: Dict[str, float] = {
        "sharpe_ratio": sharpe_ratio(returns),
        "annualized_return": annualized_return(returns),
        "max_drawdown": max_drawdown(returns),
        "calmar_ratio": calmar_ratio(returns),
        "annualized_volatility": float(np.std(returns) * np.sqrt(252)) if len(returns) > 1 else 0.0,
        "total_return": float(np.prod(1 + returns) - 1) if len(returns) > 0 else 0.0,
        "num_trades": len(returns),
    }

    if predictions is not None and actuals is not None and len(predictions) > 1:
        metrics["information_coefficient"] = information_coefficient(predictions, actuals)
        metrics["rank_ic"] = rank_ic(predictions, actuals)
        metrics["directional_accuracy"] = directional_accuracy(predictions, actuals)

    if pnl is not None and len(pnl) > 0:
        metrics["win_rate"] = win_rate(pnl)
        metrics["profit_factor"] = profit_factor(pnl)

    return metrics
