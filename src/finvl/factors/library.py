"""
Factor Library: loads self-evolved factors from best_factor.json
and supplements with pandas_ta traditional indicators.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class Factor:
    """Single factor definition."""

    def __init__(self, name: str, category: str, compute_fn: Callable, ir: float = 0.0):
        self.name = name
        self.category = category
        self.compute_fn = compute_fn
        self.ir = ir

    def compute(self, df: pd.DataFrame) -> pd.Series:
        try:
            return self.compute_fn(df)
        except Exception as e:
            logger.warning(f"Factor {self.name} computation failed: {e}")
            return pd.Series(0.0, index=df.index)


class FactorLibrary:
    """
    Manages the full factor universe:
    - Self-evolved factors from best_factor.json (~160)
    - Traditional technical factors via pandas_ta
    - Geometric factors from chart analysis
    """

    def __init__(self, factor_json_path: str = "docs/best_factor.json"):
        self.factors: Dict[str, Factor] = {}
        self._load_evolved_factors(factor_json_path)
        self._register_traditional_factors()
        logger.info(f"FactorLibrary initialized: {len(self.factors)} factors")

    def _load_evolved_factors(self, path: str):
        """Load self-evolved factors from JSON (one JSON object per line)."""
        p = Path(path)
        if not p.exists():
            logger.warning(f"Factor file not found: {path}")
            return

        from finvl.factors.dsl_engine import FactorDSL
        self._dsl = FactorDSL()

        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line == "null":
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not item:
                    continue
                name = item.get("name", "")
                if not name:
                    continue
                expr = item.get("expr", "")
                ir = float(item.get("Information_Ratio_with_cost", 0))
                category = "evolved"

                if expr:
                    fn = self._make_dsl_fn(expr)
                else:
                    fn = self._make_placeholder_fn(name)
                self.factors[name] = Factor(name, category, fn, ir)

    def _make_dsl_fn(self, expr: str) -> Callable:
        """Build compute function using DSL engine."""
        dsl = self._dsl
        def compute(df: pd.DataFrame) -> pd.Series:
            return dsl.evaluate(expr, df)
        return compute

    def _make_placeholder_fn(self, name: str) -> Callable:
        """Create a placeholder that returns zeros."""
        def compute(df: pd.DataFrame) -> pd.Series:
            return pd.Series(0.0, index=df.index)
        return compute

    def _register_traditional_factors(self):
        """Register standard technical indicators."""
        traditional = {
            "RSI_14": lambda df: self._rsi(df["close"], 14),
            "MACD_HIST": lambda df: self._macd_hist(df["close"]),
            "BB_POSITION": lambda df: self._bb_position(df["close"]),
            "ATR_NORM": lambda df: self._atr_norm(df),
            "VOLUME_RATIO": lambda df: df["volume"] / df["volume"].rolling(20).mean().fillna(1),
            "MOM_5": lambda df: df["close"].pct_change(5).fillna(0),
            "MOM_20": lambda df: df["close"].pct_change(20).fillna(0),
            "VOLATILITY_20": lambda df: df["close"].pct_change().rolling(20).std().fillna(0) * np.sqrt(252),
            "SMA_CROSS": lambda df: (df["close"].rolling(5).mean() - df["close"].rolling(20).mean()).fillna(0),
            "PRICE_ZSCORE": lambda df: ((df["close"] - df["close"].rolling(20).mean()) / df["close"].rolling(20).std().replace(0, 1)).fillna(0),
        }
        for name, fn in traditional.items():
            self.factors[name] = Factor(name, "traditional", fn, ir=0.0)

    @staticmethod
    def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
        delta = series.diff()
        gain = delta.clip(lower=0).rolling(period).mean()
        loss = (-delta.clip(upper=0)).rolling(period).mean()
        rs = gain / loss.replace(0, np.nan)
        return (100 - 100 / (1 + rs)).fillna(50) / 100.0

    @staticmethod
    def _macd_hist(series: pd.Series) -> pd.Series:
        ema12 = series.ewm(span=12).mean()
        ema26 = series.ewm(span=26).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9).mean()
        return (macd - signal).fillna(0)

    @staticmethod
    def _bb_position(series: pd.Series, period: int = 20) -> pd.Series:
        sma = series.rolling(period).mean()
        std = series.rolling(period).std().replace(0, 1)
        return ((series - sma) / (2 * std)).fillna(0)

    @staticmethod
    def _atr_norm(df: pd.DataFrame, period: int = 14) -> pd.Series:
        tr = pd.concat([
            df["high"] - df["low"],
            (df["high"] - df["close"].shift(1)).abs(),
            (df["low"] - df["close"].shift(1)).abs(),
        ], axis=1).max(axis=1)
        atr = tr.rolling(period).mean()
        return (atr / df["close"].replace(0, 1)).fillna(0)

    @property
    def factor_names(self) -> List[str]:
        return list(self.factors.keys())

    @property
    def num_factors(self) -> int:
        return len(self.factors)

    def compute_all(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute all factors for a given DataFrame."""
        results = {}
        for name, factor in self.factors.items():
            results[name] = factor.compute(df)
        return pd.DataFrame(results, index=df.index)

    def compute_subset(self, df: pd.DataFrame, factor_ids: List[int]) -> pd.DataFrame:
        """Compute a subset of factors by index."""
        names = self.factor_names
        selected = [names[i] for i in factor_ids if i < len(names)]
        results = {}
        for name in selected:
            results[name] = self.factors[name].compute(df)
        return pd.DataFrame(results, index=df.index)

    def get_factor_by_index(self, idx: int) -> Optional[Factor]:
        names = self.factor_names
        if 0 <= idx < len(names):
            return self.factors[names[idx]]
        return None
