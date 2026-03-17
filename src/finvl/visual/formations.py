"""
Chart formation detector for FinVL-MAS.
Detects higher-order geometric patterns: double top/bottom, head-and-shoulders, triangles.
"""

from __future__ import annotations

from typing import List

import numpy as np
import pandas as pd

from finvl.core.types import ChartFormation, FormationStage


class FormationDetector:
    """Detects common multi-bar chart formations."""

    def __init__(self, min_bars: int = 10):
        self.min_bars = min_bars

    def detect(self, df: pd.DataFrame) -> List[ChartFormation]:
        formations: List[ChartFormation] = []
        h = df["high"].values
        l = df["low"].values
        c = df["close"].values
        n = len(df)
        if n < self.min_bars:
            return formations

        formations.extend(self._double_top_bottom(h, l, c, n))
        formations.extend(self._triangle(h, l, n))
        return formations

    def _double_top_bottom(
        self, h: np.ndarray, l: np.ndarray, c: np.ndarray, n: int
    ) -> List[ChartFormation]:
        formations = []
        hi_idx = self._local_extrema(h, order=5, mode="max")
        lo_idx = self._local_extrema(l, order=5, mode="min")

        # Double top: two peaks at similar price
        if len(hi_idx) >= 2:
            for i in range(len(hi_idx) - 1):
                p1, p2 = h[hi_idx[i]], h[hi_idx[i + 1]]
                spread = abs(p1 - p2) / max(p1, 1e-8)
                gap = hi_idx[i + 1] - hi_idx[i]
                if spread < 0.02 and gap >= 5:
                    target = min(l[hi_idx[i]:hi_idx[i+1]+1])
                    stage = FormationStage.CONFIRMED if c[-1] < target else FormationStage.FORMING
                    formations.append(ChartFormation(
                        formation_type="double_top", stage=stage,
                        target_price=float(target - (p1 - target)),
                        confidence=max(0.3, 1.0 - spread * 20),
                        start_idx=int(hi_idx[i]), end_idx=int(hi_idx[i + 1]),
                    ))

        # Double bottom
        if len(lo_idx) >= 2:
            for i in range(len(lo_idx) - 1):
                p1, p2 = l[lo_idx[i]], l[lo_idx[i + 1]]
                spread = abs(p1 - p2) / max(p1, 1e-8)
                gap = lo_idx[i + 1] - lo_idx[i]
                if spread < 0.02 and gap >= 5:
                    target = max(h[lo_idx[i]:lo_idx[i+1]+1])
                    stage = FormationStage.CONFIRMED if c[-1] > target else FormationStage.FORMING
                    formations.append(ChartFormation(
                        formation_type="double_bottom", stage=stage,
                        target_price=float(target + (target - p1)),
                        confidence=max(0.3, 1.0 - spread * 20),
                        start_idx=int(lo_idx[i]), end_idx=int(lo_idx[i + 1]),
                    ))
        return formations

    def _triangle(self, h: np.ndarray, l: np.ndarray, n: int) -> List[ChartFormation]:
        formations = []
        if n < 20:
            return formations

        hi_idx = self._local_extrema(h, order=4, mode="max")
        lo_idx = self._local_extrema(l, order=4, mode="min")

        if len(hi_idx) >= 2 and len(lo_idx) >= 2:
            high_slope = (h[hi_idx[-1]] - h[hi_idx[0]]) / max(hi_idx[-1] - hi_idx[0], 1)
            low_slope = (l[lo_idx[-1]] - l[lo_idx[0]]) / max(lo_idx[-1] - lo_idx[0], 1)

            if high_slope < 0 and low_slope > 0:
                formations.append(ChartFormation(
                    formation_type="symmetrical_triangle",
                    stage=FormationStage.FORMING,
                    confidence=0.4,
                    start_idx=int(min(hi_idx[0], lo_idx[0])),
                    end_idx=int(max(hi_idx[-1], lo_idx[-1])),
                ))
            elif abs(high_slope) < 1e-6 and low_slope > 0:
                formations.append(ChartFormation(
                    formation_type="ascending_triangle",
                    stage=FormationStage.FORMING,
                    confidence=0.5,
                    start_idx=int(min(hi_idx[0], lo_idx[0])),
                    end_idx=int(max(hi_idx[-1], lo_idx[-1])),
                ))
            elif high_slope < 0 and abs(low_slope) < 1e-6:
                formations.append(ChartFormation(
                    formation_type="descending_triangle",
                    stage=FormationStage.FORMING,
                    confidence=0.5,
                    start_idx=int(min(hi_idx[0], lo_idx[0])),
                    end_idx=int(max(hi_idx[-1], lo_idx[-1])),
                ))
        return formations

    @staticmethod
    def _local_extrema(arr: np.ndarray, order: int = 5, mode: str = "max") -> np.ndarray:
        n = len(arr)
        if n < 2 * order + 1:
            return np.array([], dtype=int)
        indices = []
        for i in range(order, n - order):
            window = arr[i - order: i + order + 1]
            if mode == "max" and arr[i] == window.max():
                indices.append(i)
            elif mode == "min" and arr[i] == window.min():
                indices.append(i)
        return np.array(indices, dtype=int)
