"""
RiskControllerAgent: Assesses risk, recommends position sizing and stop-loss levels.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

import numpy as np

from finvl.agents.base import AgentOutput, BaseFinAgent
from finvl.core.types import ChartGeometry, RegimeType

logger = logging.getLogger(__name__)


class RiskControllerAgent(BaseFinAgent):
    """
    Assesses downside risk, volatility, and position sizing.
    Conservative by design -- its job is to prevent losses.
    """

    def __init__(self, config: Dict[str, Any] | None = None):
        super().__init__("RiskController", config or {})
        self.max_position_pct = (config or {}).get("max_position_pct", 0.10)
        self.default_stop_loss_pct = (config or {}).get("default_stop_loss_pct", 0.05)

    async def process(self, inputs: Dict[str, Any], memory: Dict[str, Any]) -> AgentOutput:
        df = inputs.get("ohlcv_df")
        current_price = inputs.get("current_price", 0.0)
        geometry: ChartGeometry | None = memory.get("chart_geometry")

        if df is None or len(df) < 10:
            return AgentOutput(
                agent_name=self.name, success=False,
                result={}, confidence=0.0,
                reasoning_trace="Insufficient data for risk assessment",
            )

        close = df["close"].values
        if current_price <= 0:
            current_price = float(close[-1])

        # Volatility assessment
        returns = np.diff(close) / close[:-1]
        vol_20 = float(np.std(returns[-20:])) if len(returns) >= 20 else float(np.std(returns))
        vol_ann = vol_20 * np.sqrt(252)
        hist_vol = float(np.std(returns))
        vol_percentile = min(vol_20 / max(hist_vol, 1e-8), 2.0) / 2.0

        # Stop-loss based on support levels or ATR
        atr_14 = self._compute_atr(df, 14)
        stop_loss = current_price - 2.0 * atr_14

        # Use nearest support if available from geometry
        if geometry and geometry.support_resistance:
            supports = [
                sr.price for sr in geometry.support_resistance
                if sr.level_type == "support" and sr.price < current_price
            ]
            if supports:
                nearest_support = max(supports)
                stop_loss = max(stop_loss, nearest_support * 0.99)

        # Take profit using resistance
        take_profit = current_price + 3.0 * atr_14
        if geometry and geometry.support_resistance:
            resistances = [
                sr.price for sr in geometry.support_resistance
                if sr.level_type == "resistance" and sr.price > current_price
            ]
            if resistances:
                take_profit = min(take_profit, min(resistances) * 0.99)

        rr_ratio = (take_profit - current_price) / max(current_price - stop_loss, 1e-8)

        # Risk level
        risk_factors = []
        if vol_percentile > 0.8:
            risk_factors.append("High volatility regime")
        if geometry and geometry.regime.regime == RegimeType.VOLATILE:
            risk_factors.append("Volatile market regime")

        max_dd_20 = self._max_drawdown(close[-20:])
        if max_dd_20 > 0.05:
            risk_factors.append(f"Recent drawdown {max_dd_20:.1%}")

        if len(risk_factors) >= 2:
            risk_level = "high"
        elif len(risk_factors) == 1:
            risk_level = "moderate"
        else:
            risk_level = "low"

        # Position sizing (scale down in high risk)
        risk_mult = {"low": 1.0, "moderate": 0.6, "high": 0.3, "extreme": 0.1}
        position_pct = self.max_position_pct * risk_mult.get(risk_level, 0.5)

        # Recommendation
        if risk_level == "high" and rr_ratio < 1.5:
            recommendation = "avoid"
        elif risk_level == "high":
            recommendation = "reduce_size"
        elif rr_ratio < 1.0:
            recommendation = "reduce_size"
        else:
            recommendation = "proceed"

        confidence = 0.7 if len(df) >= 60 else 0.4

        result = {
            "risk_level": risk_level,
            "stop_loss": float(stop_loss),
            "take_profit": float(take_profit),
            "risk_reward_ratio": float(rr_ratio),
            "max_position_pct": float(position_pct),
            "volatility_ann": float(vol_ann),
            "volatility_percentile": float(vol_percentile),
            "atr_14": float(atr_14),
            "risk_factors": risk_factors,
            "recommendation": recommendation,
        }

        self.write_to_memory("risk_level", risk_level, confidence=confidence)
        self.write_to_memory("risk_assessment", result, confidence=confidence)
        self.write_to_memory("position_size_pct", position_pct, confidence=confidence)

        reasoning = (
            f"Risk={risk_level}, Vol={vol_ann:.1%}, ATR={atr_14:.2f}, "
            f"R:R={rr_ratio:.2f}, Position={position_pct:.1%}, Rec={recommendation}"
        )
        return AgentOutput(
            agent_name=self.name, success=True,
            result=result, confidence=confidence,
            reasoning_trace=reasoning,
        )

    @staticmethod
    def _compute_atr(df, period: int = 14) -> float:
        h = df["high"].values
        l = df["low"].values
        c = df["close"].values
        n = len(df)
        if n < 2:
            return float(h[-1] - l[-1]) if n == 1 else 0.0
        tr = np.zeros(n)
        tr[0] = h[0] - l[0]
        for i in range(1, n):
            tr[i] = max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
        k = min(period, n)
        return float(np.mean(tr[-k:]))

    @staticmethod
    def _max_drawdown(prices) -> float:
        peak = prices[0]
        max_dd = 0.0
        for p in prices:
            if p > peak:
                peak = p
            dd = (peak - p) / max(peak, 1e-8)
            if dd > max_dd:
                max_dd = dd
        return float(max_dd)
