"""
DecisionPMAgent: Final portfolio manager that integrates all agent outputs
and produces a DecisionOutput (buy/sell/hold with rationale).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import numpy as np

from finvl.agents.base import AgentOutput, BaseFinAgent
from finvl.core.types import Action, Conviction, DecisionOutput, Implication

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

    def _get_factor_lib(self):
        if self._factor_lib is None:
            try:
                from finvl.factors.library import FactorLibrary
                self._factor_lib = FactorLibrary("docs/best_factor.json")
                # Select top-k factors by IR
                sorted_factors = sorted(
                    self._factor_lib.factors.values(),
                    key=lambda f: f.ir, reverse=True
                )
                # Use ALL evolved factors with IR >= 0.5 (paper: 160+ factor library)
                self._top_factors = [f for f in sorted_factors if f.ir >= 0.5]
                if len(self._top_factors) < 50:
                    # Fallback: use all available factors
                    self._top_factors = sorted_factors
                # Try to load trained router
                self._router = None
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
                        self._all_factors = sorted_factors[:cfg['num_factors']]
                        logger.info(f"Factor Router loaded (top_k={cfg['top_k']})")
                except Exception as e:
                    logger.debug(f"Router not available: {e}")
                logger.info(f"Loaded {len(self._top_factors)} top factors (IR>=1.0)")
            except Exception as e:
                logger.warning(f"Failed to load factor library: {e}")
                self._top_factors = []
        return self._top_factors

    async def process(self, inputs: Dict[str, Any], memory: Dict[str, Any]) -> AgentOutput:
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
        vol20 = 0.2
        ret_20d = 0.0
        has_edge = False
        if ohlcv_df is not None and len(ohlcv_df) >= 20:
            close = ohlcv_df["close"].values
            high = ohlcv_df["high"].values
            low = ohlcv_df["low"].values
            volume = ohlcv_df["volume"].values if "volume" in ohlcv_df.columns else np.ones(len(close))

            sma20 = close[-20:].mean()
            current = close[-1]

            # --- Trend signal (compute from SMA + returns) ---
            ret_20d = (current - close[-20]) / (close[-20] + 1e-8) if len(close) >= 20 else 0
            ret_5d = (current - close[-5]) / (close[-5] + 1e-8) if len(close) >= 5 else 0
            pvsma = (current - sma20) / (sma20 + 1e-8)
            trend_bias = np.clip(
                0.4 * np.sign(pvsma) * min(abs(pvsma) * 5, 1) +
                0.4 * np.sign(ret_20d) * min(abs(ret_20d) * 5, 1) +
                0.2 * np.sign(ret_5d) * min(abs(ret_5d) * 10, 1),
                -1, 1
            )

            # === Evolved factor signals (from best_factor.json via DSL engine) ===
            top_factors = self._get_factor_lib()
            factor_values = []
            if top_factors and len(ohlcv_df) >= 30:
                df_for_factors = ohlcv_df.copy()
                df_for_factors.columns = [c.lower() for c in df_for_factors.columns]
                for f in top_factors:  # use full evolved factor library
                    try:
                        vals = f.compute(df_for_factors)
                        last_val = vals.iloc[-1] if len(vals) > 0 else 0
                        if np.isfinite(last_val) and last_val != 0:
                            factor_values.append((last_val, f.ir))
                    except:
                        pass

            # Compute IR-weighted factor consensus signal (paper: factor router IR weighting)
            if factor_values:
                vals = np.array([v for v, ir in factor_values])
                irs = np.array([ir for v, ir in factor_values])
                vz = (vals - np.nanmean(vals)) / (np.nanstd(vals) + 1e-12)
                signs = np.sign(vz)
                signs[np.abs(vz) < 0.5] = 0
                weighted_sum = np.sum(signs * irs)
                total_ir = np.sum(irs) + 1e-12
                factor_bias = np.clip(weighted_sum / total_ir * 2, -1.0, 1.0)
            else:
                factor_bias = 0.0

            # Volatility for RASW and EGA
            if len(close) >= 21:
                daily_rets = np.diff(close[-21:]) / close[-21:-1]
                vol20 = np.std(daily_rets) * np.sqrt(252)

            # --- RASW: Regime-Adaptive Signal Weighting ---
            if vol20 > 0.35:
                w_trend, w_factor = 0.3, 0.7
            elif abs(ret_20d) > 0.08:
                w_trend, w_factor = 0.7, 0.3
            else:
                w_trend, w_factor = 0.5, 0.5

            # --- EGA: Edge-Gated Abstention ---
            has_edge = (vol20 > 0.25) or (abs(ret_20d) > 0.05)

            trend_bias = max(-1.0, min(1.0, trend_bias))

        # Score biases: bullish=+1, bearish=-1, neutral=0
        bias_map = {"bullish": 1.0, "bearish": -1.0, "neutral": 0.0}

        # Use RASW weights for trend/factor when available
        if ohlcv_df is not None and len(ohlcv_df) >= 20:
            signals = [
                ("chart", bias_map.get(chart_bias, 0.0), chart_confidence * 0.3),
                ("pattern", bias_map.get(pattern_bias, 0.0), pattern_confidence * 0.2),
                ("event", bias_map.get(event_bias, 0.0), event_confidence),
                ("trend", trend_bias, w_trend),
                ("factors", factor_bias, w_factor),
            ]
        else:
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

        # Determine action with EGA (Edge-Gated Abstention)
        if has_edge:
            # In edge regime: use moderate thresholds
            if adjusted_score > 0.10:
                action = Action.BUY
            elif adjusted_score < -0.20:
                action = Action.SELL
            else:
                action = Action.HOLD
        else:
            # No edge: require much stronger signal to trade
            if adjusted_score > 0.30:
                action = Action.BUY
            elif adjusted_score < -0.40:
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
