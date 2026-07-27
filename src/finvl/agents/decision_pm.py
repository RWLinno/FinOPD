"""
DecisionPMAgent: Final portfolio manager that integrates all agent outputs
and produces a DecisionOutput (buy/sell/hold with rationale).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import numpy as np

from finvl.agents.base import AgentOutput, BaseFinAgent
from finvl.core.types import Action, Conviction, DecisionOutput

logger = logging.getLogger(__name__)


class DecisionPMAgent(BaseFinAgent):
    """
    Integrates evidence from all prior agents via shared memory
    and produces a final trading decision with rationale.
    """

    def __init__(self, config: Dict[str, Any] | None = None):
        super().__init__("DecisionPM", config or {})
        self.integration_mode = (config or {}).get("integration_mode", "confidence_weighted")
        self._factor_lib = None
        self._top_factors = None
        self._router = None
        self._last_factor_ids: List[int] = []
        self._last_router_features: List[float] = []
        self._last_router_regime: List[float] = []
        self._last_router_selected_indices: List[int] = []
        self._router_factor_names: List[str] = []

    def _get_factor_lib(self):
        if self._factor_lib is None:
            try:
                from finvl.factors.library import FactorLibrary
                self._factor_lib = FactorLibrary()
                # Select top-k factors by IR
                sorted_factors = sorted(
                    self._factor_lib.factors.values(),
                    key=lambda f: f.ir, reverse=True
                )
                self._top_factors = [f for f in sorted_factors if f.ir >= 1.0][:30]
                factor_ids = {
                    name: index
                    for index, name in enumerate(self._factor_lib.factor_names)
                }
                self._factor_id_by_name = factor_ids
                # Try to load trained router
                try:
                    import torch
                    from finvl.factors.router import FactorRouter
                    from pathlib import Path
                    router_path = Path("outputs/router/router_best.pt")
                    config_path = Path("outputs/router/router_config.pt")
                    if router_path.exists() and config_path.exists():
                        cfg = torch.load(config_path, weights_only=False)
                        self._router = FactorRouter(
                            geometry_dim=768, regime_dim=4,
                            num_factors=cfg['num_factors'],
                            hidden_dim=256, top_k=cfg['top_k']
                        )
                        self._router.load_state_dict(torch.load(router_path, weights_only=False))
                        self._router.eval()
                        factor_names = cfg.get("factor_names", [])
                        if len(factor_names) != cfg["num_factors"]:
                            raise ValueError("router checkpoint has no ordered factor manifest")
                        self._all_factors = [
                            self._factor_lib.factors[name] for name in factor_names
                        ]
                        self._router_factor_names = list(factor_names)
                        logger.info(f"Factor Router loaded (top_k={cfg['top_k']})")
                except Exception as e:
                    logger.debug(f"Router not available: {e}")
                logger.info(f"Loaded {len(self._top_factors)} top factors (IR>=1.0)")
            except Exception as e:
                logger.warning(f"Failed to load factor library: {e}")
                self._top_factors = []
        return self._top_factors

    async def process(self, inputs: Dict[str, Any], memory: Dict[str, Any]) -> AgentOutput:
        self._last_factor_ids = []
        self._last_router_features = []
        self._last_router_regime = []
        self._last_router_selected_indices = []
        chart_bias = memory.get("chart_bias", "neutral")
        chart_confidence = memory.get("_confidence_chart_bias", 0.5)

        pattern_bias = memory.get("pattern_bias", "neutral")
        pattern_confidence = memory.get("_confidence_pattern_bias", 0.5)

        event_bias = memory.get("event_bias", "neutral")
        event_confidence = memory.get("_confidence_event_bias", 0.1)

        risk_level = memory.get("risk_level", "moderate")
        risk_confidence = memory.get("_confidence_risk_level", 0.5)
        risk_assessment = memory.get("risk_assessment", {})
        position_pct = memory.get("position_size_pct", 0.05)

        # Compute medium-term trend from price data
        ohlcv_df = inputs.get("ohlcv_df")
        trend_bias = 0.0
        factor_bias = 0.0
        if ohlcv_df is not None and len(ohlcv_df) >= 20:
            close = ohlcv_df["close"].values
            sma20 = close[-20:].mean()
            current = close[-1]
            if sma20 > 0:
                trend_bias = float(np.clip((current / sma20 - 1.0) / 0.05, -1.0, 1.0))

            # === Evolved factor signals (from the frozen artifact via DSL engine) ===
            top_factors = self._get_factor_lib()
            selected_factors = list((top_factors or [])[:20])
            if self._router is not None and len(ohlcv_df) >= 30:
                try:
                    import torch

                    df_for_router = ohlcv_df.copy()
                    df_for_router.columns = [column.lower() for column in df_for_router.columns]
                    raw_values = np.array(
                        [
                            float(factor.compute(df_for_router).iloc[-1])
                            for factor in self._all_factors
                        ],
                        dtype=np.float32,
                    )
                    raw_values[~np.isfinite(raw_values)] = 0.0
                    median = float(np.median(raw_values))
                    mad = float(np.median(np.abs(raw_values - median)))
                    normalized = np.clip(
                        (raw_values - median) / max(1.4826 * mad, 1e-6),
                        -5.0,
                        5.0,
                    )
                    geometry = np.zeros(768, dtype=np.float32)
                    geometry[: len(normalized)] = normalized
                    daily_returns = np.diff(close[-21:]) / close[-21:-1]
                    volatility = float(np.std(daily_returns) * np.sqrt(252))
                    trend = float(close[-1] / close[-20] - 1.0)
                    if volatility > 0.30:
                        regime = "volatile"
                    elif abs(trend) > 0.10:
                        regime = "trending"
                    elif volatility < 0.12:
                        regime = "calm"
                    else:
                        regime = "ranging"
                    from finvl.factors.router import encode_regime

                    regime_onehot = encode_regime(regime)
                    selected_ids = self._router.get_selected_factor_ids(
                        torch.from_numpy(geometry).unsqueeze(0),
                        regime_onehot.unsqueeze(0),
                    )[0]
                    self._last_router_features = geometry.astype(float).tolist()
                    self._last_router_regime = regime_onehot.tolist()
                    self._last_router_selected_indices = list(selected_ids)
                    selected_factors = [self._all_factors[index] for index in selected_ids]
                except Exception as exc:
                    logger.warning("Router inference failed; using frozen IR order: %s", exc)
            self._last_factor_ids = [
                self._factor_id_by_name[factor.name]
                for factor in selected_factors
            ]
            factor_values = []
            if selected_factors and len(ohlcv_df) >= 30:
                df_for_factors = ohlcv_df.copy()
                df_for_factors.columns = [c.lower() for c in df_for_factors.columns]
                for f in selected_factors:
                    try:
                        vals = f.compute(df_for_factors)
                        last_val = vals.iloc[-1] if len(vals) > 0 else 0
                        if np.isfinite(last_val) and last_val != 0:
                            factor_values.append(last_val)
                    except Exception as exc:
                        logger.debug("Factor %s failed: %s", f.name, exc)

            # Compute factor consensus signal
            if factor_values:
                # Normalize: positive values = bullish, negative = bearish
                fv = np.array(factor_values)
                # Z-score normalize
                fv_z = (fv - np.nanmean(fv)) / (np.nanstd(fv) + 1e-12)
                # Fraction of factors that are positive
                pos_frac = np.sum(fv_z > 0.5) / len(fv_z)
                neg_frac = np.sum(fv_z < -0.5) / len(fv_z)
                factor_bias = np.clip((pos_frac - neg_frac) * 2, -1.0, 1.0)
            else:
                factor_bias = 0.0

            # Volatility regime: reduce conviction in high vol
            if len(close) >= 21:
                daily_rets = np.diff(close[-21:]) / close[-21:-1]
                vol20 = np.std(daily_rets) * np.sqrt(252)
                if vol20 > 0.35:
                    trend_bias *= 0.5
                    factor_bias *= 0.5

            trend_bias = max(-1.0, min(1.0, trend_bias))

        # Score biases: bullish=+1, bearish=-1, neutral=0
        bias_map = {"bullish": 1.0, "bearish": -1.0, "neutral": 0.0}
        signals = [
            ("chart", bias_map.get(chart_bias, 0.0), chart_confidence * 0.4),
            ("pattern", bias_map.get(pattern_bias, 0.0), pattern_confidence * 0.3),
            ("event", bias_map.get(event_bias, 0.0), event_confidence),
            ("trend", trend_bias, 0.6),
            ("factors", factor_bias, 0.8),
        ]

        # Confidence-weighted score
        weighted_score = 0.0
        total_conf = 0.0
        for name, score, conf in signals:
            weighted_score += score * conf
            total_conf += conf

        if total_conf > 0:
            normalized_score = weighted_score / total_conf
        else:
            normalized_score = 0.0

        # Apply risk filter
        risk_mult = {"low": 1.0, "moderate": 0.8, "high": 0.5, "extreme": 0.2}
        risk_factor = risk_mult.get(risk_level, 0.5)
        adjusted_score = normalized_score * risk_factor

        # Determine action with asymmetric thresholds
        # In trend-following: easier to buy (follow trend), harder to sell (against trend)
        if adjusted_score > 0.15:
            action = Action.BUY
        elif adjusted_score < -0.3:
            action = Action.SELL
        else:
            action = Action.HOLD

        # Risk recommendation override
        recommendation = risk_assessment.get("recommendation", "proceed")
        if recommendation == "avoid":
            action = Action.HOLD
            adjusted_score = 0.0

        # Conviction
        abs_score = abs(adjusted_score)
        if abs_score > 0.6:
            conviction = Conviction.HIGH
        elif abs_score > 0.3:
            conviction = Conviction.MODERATE
        else:
            conviction = Conviction.LOW

        # Detect contradictions
        disagreements = self._detect_disagreements(signals)

        # Build rationale
        rationale_parts = [
            f"Chart analysis ({chart_bias}, conf={chart_confidence:.2f})",
            f"Pattern analysis ({pattern_bias}, conf={pattern_confidence:.2f})",
            f"Event context ({event_bias}, conf={event_confidence:.2f})",
            f"Risk level: {risk_level} (rec={recommendation})",
            f"Weighted score: {normalized_score:.3f}, risk-adjusted: {adjusted_score:.3f}",
        ]
        if disagreements:
            rationale_parts.append(f"Disagreements: {'; '.join(disagreements)}")
        rationale = " | ".join(rationale_parts)

        # Scale confidence proportionally to signal strength.
        # A HOLD with abs_score near 0 should yield low confidence.
        confidence = min(abs_score * 0.8 + 0.1, 0.95) if abs_score > 0.05 else 0.1

        decision = DecisionOutput(
            action=action,
            conviction=conviction,
            position_size_pct=self._adjust_position_size(
                float(position_pct), conviction, risk_level
            ) if action != Action.HOLD else 0.0,
            stop_loss=risk_assessment.get("stop_loss"),
            take_profit=risk_assessment.get("take_profit"),
            confidence=confidence,
            rationale=rationale,
            key_evidence=[f"{name}: {score:+.2f}" for name, score, _ in signals],
            risks_acknowledged=risk_assessment.get("risk_factors", []),
            contradictions_resolved="; ".join(disagreements) if disagreements else "None",
            agent_confidences={
                "chart": chart_confidence,
                "pattern": pattern_confidence,
                "event": event_confidence,
                "risk": risk_confidence,
            },
        )

        self.write_to_memory("decision", decision, confidence=confidence)

        return AgentOutput(
            agent_name=self.name,
            success=True,
            result={
                "action": action.value,
                "conviction": conviction.value,
                "confidence": confidence,
                "position_pct": decision.position_size_pct,
                "weighted_score": adjusted_score,
            },
            confidence=confidence,
            reasoning_trace=rationale,
        )

    @staticmethod
    def _adjust_position_size(
        base_pct: float, conviction: Conviction, risk_level: str,
    ) -> float:
        """Scale position size by conviction and risk level."""
        conviction_mult = {Conviction.HIGH: 1.0, Conviction.MODERATE: 0.7, Conviction.LOW: 0.4}
        risk_mult = {"low": 1.2, "moderate": 1.0, "high": 0.5, "extreme": 0.1}
        return base_pct * conviction_mult.get(conviction, 0.5) * risk_mult.get(risk_level, 0.5)

    def _detect_disagreements(
        self, signals: List[tuple[str, float, float]]
    ) -> List[str]:
        disagreements = []
        for i, (n1, s1, c1) in enumerate(signals):
            for n2, s2, c2 in signals[i + 1:]:
                if s1 * s2 < 0 and min(c1, c2) > 0.3:
                    dir1 = "bullish" if s1 > 0 else "bearish"
                    dir2 = "bullish" if s2 > 0 else "bearish"
                    disagreements.append(f"{n1}({dir1}) vs {n2}({dir2})")
        return disagreements
