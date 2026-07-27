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
    policy_prompt: str = ""
    policy_completion: str = ""
    factor_ids: List[int] = field(default_factory=list)
    router_features: List[float] = field(default_factory=list)
    router_regime: List[float] = field(default_factory=list)
    router_selected_indices: List[int] = field(default_factory=list)


@dataclass
class Trajectory:
    """Complete rollout trajectory with post-hoc metrics."""
    asset: str
    steps: List[TrajectoryStep] = field(default_factory=list)
    metrics: Dict[str, float] = field(default_factory=dict)
    agent_contributions: Dict[str, float] = field(default_factory=dict)
    available_date: str = ""

    @property
    def length(self) -> int:
        return len(self.steps)

    @property
    def score(self) -> float:
        return self.metrics.get("utility", float("-inf"))


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
        belief_index=None,
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

            traj = self._rollout_window(
                orchestrator, provider, window_dates, asset, belief_index
            )
            if traj and traj.length >= self.min_trajectory_length:
                self._compute_posthoc_metrics(traj, provider, dates, start_idx)
                trajectories.append(traj)

        logger.info(f"Generated {len(trajectories)} trajectories for {asset}")
        return trajectories

    def _rollout_window(
        self, orchestrator, provider, dates: List[str], asset: str, belief_index=None
    ) -> Optional[Trajectory]:
        """Run orchestrator on a window of dates."""
        return self.rollout_window(
            orchestrator, provider, dates, asset, belief_index=belief_index
        )

    def rollout_window(
        self,
        orchestrator,
        provider,
        dates: List[str],
        asset: str,
        belief_index=None,
    ) -> Optional[Trajectory]:
        """Run one exact decision horizon and retain policy supervision fields."""
        import asyncio

        if orchestrator is None:
            raise ValueError("rollout requires a concrete orchestrator")

        traj = Trajectory(asset=asset)

        for date in dates:
            try:
                window_df = provider.get_window(date, lookback=60, asset=asset)
                if len(window_df) < 10:
                    continue

                state_signature = self._state_signature(window_df)
                inputs = {
                    "ohlcv_df": window_df,
                    "current_price": float(window_df["close"].iloc[-1]),
                    "asset": asset,
                    "timeframe": "daily",
                    "events": [],
                }
                if belief_index is not None and belief_index.size:
                    retrieved = belief_index.query(
                        state_signature,
                        top_k=5,
                        as_of_date=date,
                    )
                    inputs["retrieved_episodes"] = [
                        {**metadata, "similarity": similarity}
                        for metadata, similarity in retrieved
                    ]

                decision = asyncio.run(orchestrator.run(inputs))

                step = TrajectoryStep(
                    date=date,
                    observation={
                        "close": float(window_df["close"].iloc[-1]),
                        "state_signature": state_signature.astype(float).tolist(),
                    },
                    prediction=decision.rationale[:100],
                    action=decision.action.value if hasattr(decision.action, "value") else str(decision.action),
                    confidence=decision.confidence,
                    position_size=decision.position_size_pct,
                    policy_prompt=getattr(orchestrator, "last_policy_prompt", ""),
                    policy_completion=getattr(
                        orchestrator, "last_policy_completion", ""
                    ),
                    factor_ids=list(
                        getattr(orchestrator, "last_factor_ids", [])
                    ),
                    router_features=list(
                        getattr(orchestrator, "last_router_features", [])
                    ),
                    router_regime=list(
                        getattr(orchestrator, "last_router_regime", [])
                    ),
                    router_selected_indices=list(
                        getattr(orchestrator, "last_router_selected_indices", [])
                    ),
                )
                traj.steps.append(step)

            except Exception as e:
                logger.debug(f"Rollout step failed on {date}: {e}")
                continue

        return traj if traj.length > 0 else None

    @staticmethod
    def _state_signature(window_df: pd.DataFrame) -> np.ndarray:
        """Deterministic point-in-time return/volume signature."""
        closes = window_df["close"].astype(float)
        close_returns = closes.pct_change().tail(60).fillna(0.0)
        if "volume" in window_df.columns:
            volume = window_df["volume"].astype(float).tail(60)
            volume_std = float(volume.std(ddof=0))
            volume_z = (
                (volume - float(volume.mean())) / volume_std
                if volume_std > 0
                else volume * 0.0
            )
        else:
            volume_z = pd.Series(0.0, index=close_returns.index)
        return np.concatenate(
            [close_returns.to_numpy(), volume_z.to_numpy()]
        ).astype(np.float32)

    def _compute_posthoc_metrics(
        self, traj: Trajectory, provider, all_dates: List[str], start_idx: int
    ):
        """Compatibility wrapper for the public metric implementation."""
        self.compute_posthoc_metrics(traj, provider)

    def compute_posthoc_metrics(self, traj: Trajectory, provider):
        """Compute cost-aware post-horizon utility from the realized price path."""
        if not traj.steps:
            return

        from finvl.self_evolution.opsd.utility import outcome_utility

        market = provider._asset_frame(traj.asset)["close"].astype(float)
        target = np.zeros(len(market), dtype=float)
        date_to_location = {timestamp.strftime("%Y-%m-%d"): i for i, timestamp in enumerate(market.index)}
        for step in traj.steps:
            location = date_to_location.get(step.date)
            if location is None:
                continue
            direction = {"buy": 1.0, "sell": -1.0, "hold": 0.0}.get(step.action.lower(), 0.0)
            target[location] = direction * float(step.position_size)
        # Decisions at t are executed at t+1 and then held until changed.
        positions = pd.Series(target, index=market.index).replace(0.0, np.nan).ffill().fillna(0.0)
        positions = positions.shift(1).fillna(0.0)
        price_returns = market.pct_change().fillna(0.0)
        turnover_series = positions.diff().abs().fillna(positions.abs())
        cost_rate = 0.002  # 15 bps transaction cost + 5 bps slippage
        net = positions * price_returns - turnover_series * cost_rate
        selected_dates = [date for date in traj.steps if date.date in date_to_location]
        if not selected_dates:
            raise ValueError("trajectory dates do not overlap provider data")
        start = min(date_to_location[step.date] for step in selected_dates)
        end = min(len(net), max(date_to_location[step.date] for step in selected_dates) + self.forward_days + 1)
        window_returns = net.iloc[start:end].to_numpy()
        turnover = float(turnover_series.iloc[start:end].sum())
        traj.metrics = outcome_utility(window_returns, turnover)
        traj.available_date = market.index[end - 1].strftime("%Y-%m-%d")
