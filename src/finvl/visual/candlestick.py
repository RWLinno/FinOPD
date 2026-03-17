"""
Extended candlestick pattern classifier.
Detects multi-bar patterns beyond single-bar basics covered in geometry.py.
"""

from __future__ import annotations

from typing import List

import numpy as np
import pandas as pd

from finvl.core.types import CandlePattern, Implication, PatternSignificance


class CandlestickClassifier:
    """Classifies multi-bar candlestick patterns."""

    def classify(self, df: pd.DataFrame) -> List[CandlePattern]:
        patterns: List[CandlePattern] = []
        o, h, l, c = df["open"].values, df["high"].values, df["low"].values, df["close"].values
        n = len(df)
        if n < 5:
            return patterns

        patterns.extend(self._morning_evening_star(o, h, l, c, n))
        patterns.extend(self._three_soldiers_crows(o, h, l, c, n))
        return patterns

    def _morning_evening_star(
        self, o: np.ndarray, h: np.ndarray, l: np.ndarray, c: np.ndarray, n: int,
    ) -> List[CandlePattern]:
        patterns = []
        for i in range(2, min(n, max(2, n - 5) + 7)):
            body0 = abs(c[i-2] - o[i-2])
            body1 = abs(c[i-1] - o[i-1])
            body2 = abs(c[i] - o[i])
            range1 = h[i-1] - l[i-1]
            if range1 < 1e-8:
                continue

            # Morning star: big bearish, small body (star), big bullish
            if (c[i-2] < o[i-2] and body0 > 2 * body1
                    and c[i] > o[i] and body2 > 2 * body1
                    and c[i] > (o[i-2] + c[i-2]) / 2):
                patterns.append(CandlePattern(
                    pattern="morning_star", bar_index=i,
                    significance=PatternSignificance.STRONG,
                    implication=Implication.BULLISH,
                ))

            # Evening star: big bullish, small body, big bearish
            if (c[i-2] > o[i-2] and body0 > 2 * body1
                    and c[i] < o[i] and body2 > 2 * body1
                    and c[i] < (o[i-2] + c[i-2]) / 2):
                patterns.append(CandlePattern(
                    pattern="evening_star", bar_index=i,
                    significance=PatternSignificance.STRONG,
                    implication=Implication.BEARISH,
                ))
        return patterns

    def _three_soldiers_crows(
        self, o: np.ndarray, h: np.ndarray, l: np.ndarray, c: np.ndarray, n: int,
    ) -> List[CandlePattern]:
        patterns = []
        for i in range(2, min(n, max(2, n - 5) + 7)):
            # Three white soldiers
            if all(c[i-j] > o[i-j] for j in range(3)):
                if c[i] > c[i-1] > c[i-2] and o[i] > o[i-1] > o[i-2]:
                    patterns.append(CandlePattern(
                        pattern="three_white_soldiers", bar_index=i,
                        significance=PatternSignificance.STRONG,
                        implication=Implication.BULLISH,
                    ))
            # Three black crows
            if all(c[i-j] < o[i-j] for j in range(3)):
                if c[i] < c[i-1] < c[i-2] and o[i] < o[i-1] < o[i-2]:
                    patterns.append(CandlePattern(
                        pattern="three_black_crows", bar_index=i,
                        significance=PatternSignificance.STRONG,
                        implication=Implication.BEARISH,
                    ))
        return patterns
