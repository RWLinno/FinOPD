"""
Student Rollout: rolling-window trajectory sampling for OPSD.
Each trajectory records (observation, prediction, action) tuples
with post-hoc performance metrics.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class TrajectoryStep:
    """Single step in a rollout trajectory."""
    date: str
    observation: Dict[str, Any]
    prediction: str
    action: str
    confidence: float
    position_size: float


@dataclass
class Trajectory:
    """Complete rollout trajectory with post-hoc metrics."""
    asset: str
    steps: List[TrajectoryStep] = field(default_factory=list)
    metrics: Dict[str, float] = field(default_factory=dict)
    agent_contributions: Dict[str, float] = field(default_factory=dict)

    @property
    def length(self) -> int:
        return len(self.steps)

    @property
    def score(self) -> float:
        return self.metrics.get("sharpe", 0.0)


class StudentRollout:
    """
    Generates on-policy trajectories using the current student model.
    Rolling window approach: each trajectory covers a contiguous window.
    """

    def __init__(
        self,
        window_days: int = 60,
        forward_days: int = 20,
        min_trajectory_length: int = 20,
    ):
        self.window_days = window_days
        self.forward_days = forward_days
        self.min_trajectory_length = min_trajectory_length

    def generate_trajectories(
        self,
        orchestrator,
        provider,
        dates: List[str],
        asset: str,
        num_trajectories: int = 10,
    ) -> List[Trajectory]:
        """Generate multiple trajectories via rolling windows."""
        trajectories = []
        step = max(1, len(dates) // num_trajectories)

        for start_idx in range(0, len(dates) - self.window_days, step):
            if len(trajectories) >= num_trajectories:
                break

            window_dates = dates[start_idx:start_idx + self.window_days]
            if len(window_dates) < self.min_trajectory_length:
                continue

            traj = self._rollout_window(orchestrator, provider, window_dates, asset)
            if traj and traj.length >= self.min_trajectory_length:
                self._compute_posthoc_metrics(traj, provider, dates, start_idx)
                trajectories.append(traj)

        logger.info(f"Generated {len(trajectories)} trajectories for {asset}")
        return trajectories

    def _rollout_window(
        self, orchestrator, provider, dates: List[str], asset: str
    ) -> Optional[Trajectory]:
        """Run orchestrator on a window of dates."""
        import asyncio

        traj = Trajectory(asset=asset)

        for date in dates:
            try:
                window_df = provider.get_window(date, lookback=60)
                if len(window_df) < 10:
                    continue

                inputs = {
                    "ohlcv_df": window_df,
                    "current_price": float(window_df["close"].iloc[-1]),
                    "asset": asset,
                    "timeframe": "daily",
                    "events": [],
                }

                decision = asyncio.run(orchestrator.run(inputs))

                step = TrajectoryStep(
                    date=date,
                    observation={"close": float(window_df["close"].iloc[-1])},
                    prediction=decision.rationale[:100],
                    action=decision.action.value if hasattr(decision.action, "value") else str(decision.action),
                    confidence=decision.confidence,
                    position_size=decision.position_size_pct,
                )
                traj.steps.append(step)

            except Exception as e:
                logger.debug(f"Rollout step failed on {date}: {e}")
                continue

        return traj if traj.length > 0 else None

    def _compute_posthoc_metrics(
        self, traj: Trajectory, provider, all_dates: List[str], start_idx: int
    ):
        """Compute post-hoc risk-adjusted metrics for a trajectory."""
        if not traj.steps:
            return

        returns = []
        for step in traj.steps:
            signal = {"buy": 1.0, "sell": -1.0, "hold": 0.0}.get(step.action, 0.0)
            returns.append(signal * 0.01 * step.confidence)

        returns_arr = np.array(returns)
        if len(returns_arr) < 2 or returns_arr.std() < 1e-8:
            traj.metrics = {"sharpe": 0.0, "mdd": 0.0, "sortino": 0.0, "cvar": 0.0}
            return

        sharpe = float(returns_arr.mean() / returns_arr.std() * np.sqrt(252))
        cumulative = np.cumprod(1 + returns_arr)
        peak = np.maximum.accumulate(cumulative)
        mdd = float(((peak - cumulative) / peak).max())

        downside = returns_arr[returns_arr < 0]
        downside_std = downside.std() if len(downside) > 1 else 1e-8
        sortino = float(returns_arr.mean() / downside_std * np.sqrt(252))

        cvar_threshold = np.percentile(returns_arr, 5)
        cvar = float(returns_arr[returns_arr <= cvar_threshold].mean()) if any(returns_arr <= cvar_threshold) else 0.0

        traj.metrics = {
            "sharpe": sharpe,
            "mdd": mdd,
            "sortino": sortino,
            "cvar": cvar,
        }
