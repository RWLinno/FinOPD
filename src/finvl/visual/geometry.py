"""
Chart geometry extraction for FinVL-MAS.
Rule-based detection of trendlines, support/resistance levels,
candlestick patterns, and regime classification.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd

from finvl.core.types import (
    CandlePattern,
    ChartGeometry,
    Implication,
    PatternSignificance,
    PriceLevel,
    RegimeState,
    RegimeType,
    TrendDirection,
    TrendLine,
    VolumeSignal,
)

logger = logging.getLogger(__name__)


class GeometryExtractor:
    """Extracts structured chart geometry from OHLCV data."""

    def __init__(self, config: dict | None = None):
        config = config or {}
        self.tl_min_touches = config.get("trendline", {}).get("min_touches", 2)
        self.tl_window = config.get("trendline", {}).get("window", 60)
        self.sr_tol_pct = config.get("support_resistance", {}).get("tolerance_pct", 0.02)
        self.sr_min_touches = config.get("support_resistance", {}).get("min_touches", 2)
        self.candle_lookback = config.get("candlestick", {}).get("lookback", 10)

    def extract(self, df: pd.DataFrame) -> ChartGeometry:
        """Full geometry extraction pipeline."""
        trendlines = self.detect_trendlines(df)
        sr_levels = self.detect_support_resistance(df)
        candle_patterns = self.detect_candlestick_patterns(df)
        volume_signals = self.detect_volume_signals(df)
        regime = self.classify_regime(df)

        bias = self._compute_bias(trendlines, candle_patterns, regime)

        return ChartGeometry(
            trendlines=trendlines,
            support_resistance=sr_levels,
            candlestick_patterns=candle_patterns,
            formations=[],
            volume_signals=volume_signals,
            regime=regime,
            overall_bias=bias,
            confidence=0.5,
        )

    # ------------------------------------------------------------------
    # Trendlines via linear regression on local extrema
    # ------------------------------------------------------------------

    def detect_trendlines(self, df: pd.DataFrame) -> List[TrendLine]:
        lines = []
        highs = df["high"].values
        lows = df["low"].values
        n = len(df)
        if n < 10:
            return lines

        # Use multiple sub-windows so that short- and long-range
        # trendlines are both detected.
        windows = [n]
        if self.tl_window < n:
            windows.append(self.tl_window)
        half_win = self.tl_window // 2
        if half_win >= 10 and half_win < n:
            windows.append(half_win)

        seen_spans: set = set()
        for win in windows:
            start = max(0, n - win)
            h_slice = highs[start:]
            l_slice = lows[start:]

            hi_idx = self._local_extrema(h_slice, order=5, mode="max")
            lo_idx = self._local_extrema(l_slice, order=5, mode="min")

            for idx_arr, vals, is_high in [
                (hi_idx, h_slice, True), (lo_idx, l_slice, False),
            ]:
                if len(idx_arr) < self.tl_min_touches:
                    continue
                slope, intercept, r2 = self._fit_line(idx_arr, vals[idx_arr])
                if r2 <= 0.3:
                    continue
                abs_start = int(idx_arr[0]) + start
                abs_end = int(idx_arr[-1]) + start
                span_key = (abs_start, abs_end, is_high)
                if span_key in seen_spans:
                    continue
                seen_spans.add(span_key)
                if is_high:
                    direction = TrendDirection.DOWN if slope < -1e-6 else TrendDirection.UP
                else:
                    direction = TrendDirection.UP if slope > 1e-6 else TrendDirection.DOWN
                last_price = highs[-1] if is_high else lows[-1]
                expected = slope * (n - 1 - start) + intercept
                status = "broken" if (
                    (is_high and last_price > expected * 1.01) or
                    (not is_high and last_price < expected * 0.99)
                ) else "intact"
                lines.append(TrendLine(
                    direction=direction, slope=float(slope),
                    intercept=float(intercept),
                    r_squared=float(r2),
                    start_idx=abs_start, end_idx=abs_end,
                    status=status,
                    confidence=min(float(r2), 1.0),
                ))
        return lines

    # ------------------------------------------------------------------
    # Support / Resistance via price clustering
    # ------------------------------------------------------------------

    def detect_support_resistance(self, df: pd.DataFrame) -> List[PriceLevel]:
        levels: List[PriceLevel] = []
        close = df["close"].values
        high = df["high"].values
        low = df["low"].values

        price_range = high.max() - low.min()
        if price_range < 1e-8:
            return levels
        tol = price_range * self.sr_tol_pct

        pivot_prices = np.concatenate([
            high[self._local_extrema(high, order=3, mode="max")],
            low[self._local_extrema(low, order=3, mode="min")],
        ])

        if len(pivot_prices) == 0:
            return levels

        pivot_prices = np.sort(pivot_prices)
        clusters: List[List[float]] = []
        current_cluster = [pivot_prices[0]]
        for p in pivot_prices[1:]:
            if abs(p - np.mean(current_cluster)) <= tol:
                current_cluster.append(p)
            else:
                clusters.append(current_cluster)
                current_cluster = [p]
        clusters.append(current_cluster)

        current_price = close[-1]
        for cluster in clusters:
            if len(cluster) < self.sr_min_touches:
                continue
            level_price = float(np.mean(cluster))
            ltype = "support" if level_price < current_price else "resistance"
            strength = min(len(cluster) / 5.0, 1.0)
            levels.append(PriceLevel(
                price=level_price, level_type=ltype,
                strength=strength, touch_count=len(cluster),
            ))
        # Tag levels that have been broken by recent price action
        for level in levels:
            if level.level_type == "resistance" and current_price > level.price * 1.005:
                level.level_type = "broken_resistance"
            elif level.level_type == "support" and current_price < level.price * 0.995:
                level.level_type = "broken_support"
        return sorted(levels, key=lambda l: abs(l.price - current_price))

    # ------------------------------------------------------------------
    # Candlestick patterns
    # ------------------------------------------------------------------

    def detect_candlestick_patterns(self, df: pd.DataFrame) -> List[CandlePattern]:
        patterns: List[CandlePattern] = []
        o, h, l, c = df["open"].values, df["high"].values, df["low"].values, df["close"].values
        n = len(df)
        if n < 3:
            return patterns

        for i in range(max(0, n - self.candle_lookback), n):
            body = abs(c[i] - o[i])
            full_range = h[i] - l[i]
            if full_range < 1e-8:
                continue
            body_ratio = body / full_range
            upper_shadow = h[i] - max(o[i], c[i])
            lower_shadow = min(o[i], c[i]) - l[i]

            # Doji
            if body_ratio < 0.1:
                patterns.append(CandlePattern(
                    pattern="doji", bar_index=i,
                    significance=PatternSignificance.MODERATE,
                    implication=Implication.NEUTRAL,
                ))

            # Hammer (bullish reversal)
            if lower_shadow > 2 * body and upper_shadow < body and c[i] > o[i]:
                patterns.append(CandlePattern(
                    pattern="hammer", bar_index=i,
                    significance=PatternSignificance.MODERATE,
                    implication=Implication.BULLISH,
                ))

            # Shooting star (bearish reversal)
            if upper_shadow > 2 * body and lower_shadow < body and c[i] < o[i]:
                patterns.append(CandlePattern(
                    pattern="shooting_star", bar_index=i,
                    significance=PatternSignificance.MODERATE,
                    implication=Implication.BEARISH,
                ))

            # Bullish engulfing
            if i > 0 and c[i - 1] < o[i - 1] and c[i] > o[i]:
                prev_body = abs(c[i - 1] - o[i - 1])
                if body > prev_body and o[i] <= c[i - 1] and c[i] >= o[i - 1]:
                    patterns.append(CandlePattern(
                        pattern="engulfing_bullish", bar_index=i,
                        significance=PatternSignificance.STRONG,
                        implication=Implication.BULLISH,
                    ))

            # Bearish engulfing
            if i > 0 and c[i - 1] > o[i - 1] and c[i] < o[i]:
                prev_body = abs(c[i - 1] - o[i - 1])
                if body > prev_body and o[i] >= c[i - 1] and c[i] <= o[i - 1]:
                    patterns.append(CandlePattern(
                        pattern="engulfing_bearish", bar_index=i,
                        significance=PatternSignificance.STRONG,
                        implication=Implication.BEARISH,
                    ))

        return patterns

    # ------------------------------------------------------------------
    # Volume signals
    # ------------------------------------------------------------------

    def detect_volume_signals(self, df: pd.DataFrame) -> List[VolumeSignal]:
        signals: List[VolumeSignal] = []
        vol = df["volume"].values
        close = df["close"].values
        n = len(df)
        if n < 20:
            return signals

        avg_vol = np.mean(vol[-20:])
        if avg_vol < 1e-8:
            return signals

        # Climax volume (>2x average at end)
        for i in range(max(0, n - 5), n):
            if vol[i] > 2.0 * avg_vol:
                signals.append(VolumeSignal(
                    signal_type="climax", bar_index=i,
                    implication=Implication.NEUTRAL,
                    description=f"Volume {vol[i]/avg_vol:.1f}x average",
                ))

        # Price-volume divergence (price up but volume declining over last 10 bars)
        if n >= 10:
            price_change = close[-1] - close[-10]
            vol_change = np.mean(vol[-5:]) - np.mean(vol[-10:-5])
            if price_change > 0 and vol_change < -0.2 * avg_vol:
                signals.append(VolumeSignal(
                    signal_type="bearish_divergence", bar_index=n - 1,
                    implication=Implication.BEARISH,
                    description="Price rising on declining volume",
                ))
            elif price_change < 0 and vol_change < -0.2 * avg_vol:
                signals.append(VolumeSignal(
                    signal_type="dry_up", bar_index=n - 1,
                    implication=Implication.BULLISH,
                    description="Price falling on declining volume (potential exhaustion)",
                ))
        return signals

    # ------------------------------------------------------------------
    # Regime classification
    # ------------------------------------------------------------------

    def classify_regime(self, df: pd.DataFrame) -> RegimeState:
        close = df["close"].values
        n = len(close)
        if n < 20:
            return RegimeState()

        returns = np.diff(close) / close[:-1]
        vol_20 = float(np.std(returns[-20:]))
        vol_full = float(np.std(returns)) if len(returns) > 20 else vol_20
        vol_pct = min(vol_20 / max(vol_full, 1e-8), 2.0) / 2.0

        sma20 = np.mean(close[-20:])
        sma5 = np.mean(close[-5:])
        trend_strength = (sma5 - sma20) / max(sma20, 1e-8)

        if vol_pct > 0.7:
            regime = RegimeType.VOLATILE
        elif abs(trend_strength) < 0.01:
            regime = RegimeType.RANGING
        elif trend_strength > 0.02:
            regime = RegimeType.TRENDING_UP
        elif trend_strength < -0.02:
            regime = RegimeType.TRENDING_DOWN
        else:
            regime = RegimeType.QUIET

        return RegimeState(
            regime=regime,
            trend_strength=float(trend_strength),
            volatility_percentile=float(vol_pct),
        )

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _local_extrema(arr: np.ndarray, order: int = 5, mode: str = "max") -> np.ndarray:
        """Find local maxima or minima indices, keeping only the first
        index in any consecutive run of equal-valued extrema."""
        n = len(arr)
        if n < 2 * order + 1:
            return np.array([], dtype=int)
        indices = []
        for i in range(order, n - order):
            window = arr[i - order: i + order + 1]
            is_extremum = (
                (mode == "max" and arr[i] == window.max()) or
                (mode == "min" and arr[i] == window.min())
            )
            if is_extremum:
                if indices and arr[indices[-1]] == arr[i] and i - indices[-1] <= order:
                    continue
                indices.append(i)
        return np.array(indices, dtype=int)

    @staticmethod
    def _fit_line(x_idx: np.ndarray, y_vals: np.ndarray) -> Tuple[float, float, float]:
        """Fit a line via least squares. Returns (slope, intercept, r^2)."""
        x = x_idx.astype(float)
        y = y_vals.astype(float)
        n = len(x)
        if n < 2:
            return 0.0, float(y.mean()) if n else 0.0, 0.0
        A = np.vstack([x, np.ones(n)]).T
        result = np.linalg.lstsq(A, y, rcond=None)
        slope, intercept = result[0]
        y_pred = slope * x + intercept
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - y.mean()) ** 2)
        r2 = 1.0 - ss_res / max(ss_tot, 1e-8)
        return float(slope), float(intercept), float(max(r2, 0.0))

    def _compute_bias(
        self,
        trendlines: List[TrendLine],
        patterns: List[CandlePattern],
        regime: RegimeState,
    ) -> Implication:
        score = 0.0
        for tl in trendlines:
            if tl.direction == TrendDirection.UP:
                score += tl.confidence
            else:
                score -= tl.confidence
        for p in patterns:
            if p.implication == Implication.BULLISH:
                score += 0.3
            elif p.implication == Implication.BEARISH:
                score -= 0.3
        if regime.regime == RegimeType.TRENDING_UP:
            score += 0.2
        elif regime.regime == RegimeType.TRENDING_DOWN:
            score -= 0.2

        if score > 0.3:
            return Implication.BULLISH
        elif score < -0.3:
            return Implication.BEARISH
        return Implication.NEUTRAL
