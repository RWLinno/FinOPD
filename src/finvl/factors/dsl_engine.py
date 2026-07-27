"""
Factor DSL Engine: evaluates factor expressions from best_factor.json.
Implements all 45 DSL functions used in the evolved factor library.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Callable, Dict

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class FactorDSL:
    """Evaluates factor expressions written in the FinOPD DSL."""

    def __init__(self):
        self._fn_registry: Dict[str, Callable] = {}
        self._register_all()

    def evaluate(self, expr: str, df: pd.DataFrame) -> pd.Series:
        """Evaluate a factor expression on OHLCV DataFrame."""
        try:
            env = self._build_env(df)
            result = self._eval_expr(expr, env)
            if isinstance(result, (int, float, bool)):
                return pd.Series(float(result), index=df.index)
            if isinstance(result, np.ndarray):
                return pd.Series(result, index=df.index).replace([np.inf, -np.inf], np.nan).fillna(0.0)
            if isinstance(result, pd.Series):
                return result.replace([np.inf, -np.inf], np.nan).fillna(0.0)
            return pd.Series(0.0, index=df.index)
        except Exception as e:
            logger.debug(f"Factor eval failed: {e}")
            return pd.Series(0.0, index=df.index)

    def _build_env(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Build evaluation environment with data columns and functions."""
        env = {"__builtins__": {}}
        # Data columns
        cols = df.columns.str.lower()
        df_lower = df.copy()
        df_lower.columns = cols
        for c in ['close', 'open', 'high', 'low', 'volume']:
            if c in df_lower.columns:
                env[f'${c}'] = df_lower[c].values.astype(float)
        # Derived
        if 'close' in df_lower.columns:
            env['$return'] = np.concatenate([[0], np.diff(df_lower['close'].values) / (df_lower['close'].values[:-1] + 1e-12)])
            env['$change'] = df_lower['close'].values - df_lower['open'].values
        # Optional columns (set to zeros if missing)
        for c in ['amount', 'buy_sm_vol', 'sell_sm_vol', 'buy_lg_vol', 'sell_lg_vol',
                  'buy_md_vol', 'sell_md_vol', 'buy_elg_amount', 'net_mf_vol',
                  'bench_close', 'bench_return', 'industry', 'chip_conct_70',
                  'cost_15pct', 'cost_50pct']:
            key = f'${c}'
            if c in df_lower.columns:
                env[key] = df_lower[c].values.astype(float)
            else:
                env[key] = np.zeros(len(df_lower))
        # Register all DSL functions
        env.update(self._fn_registry)
        # Python builtins needed
        env['nan'] = np.nan
        env['np'] = np
        return env

    def _eval_expr(self, expr: str, env: Dict) -> Any:
        """Safely evaluate expression."""
        safe_expr = expr
        # Replace $ variables with valid Python names
        safe_expr = re.sub(r'\$(\w+)', r'_col_\1', safe_expr)
        # Replace ternary (cond) ? val1 : val2 with np.where(cond, val1, val2)
        # Handle nested ternary
        for _ in range(5):
            m = re.search(r'(\([^()]*\))\s*\?\s*([^:?]+)\s*:\s*([^,)]+)', safe_expr)
            if m:
                cond, val1, val2 = m.group(1), m.group(2).strip(), m.group(3).strip()
                replacement = f'np.where({cond}, {val1}, {val2})'
                safe_expr = safe_expr[:m.start()] + replacement + safe_expr[m.end():]
            else:
                break
        # Simple ternary without parens: expr ? val1 : val2
        safe_expr = re.sub(r'([^,\s]+)\s*\?\s*([^:]+)\s*:\s*([^,\)]+)', r'np.where(\1, \2, \3)', safe_expr)
        # Fix & and | operators for numpy arrays
        safe_expr = safe_expr.replace(' & ', ') * (')
        safe_expr = safe_expr.replace('&', ') * (')
        # Wrap conditions in parens for multiplication
        safe_expr = re.sub(r'\((\s*\))\s*\*\s*\((\s*\))', r'(\1) * (\2)', safe_expr)

        # Rename env keys
        new_env = {}
        for k, v in env.items():
            if k.startswith('$'):
                new_env[f'_col_{k[1:]}'] = v
            else:
                new_env[k] = v
        return eval(safe_expr, {"__builtins__": {}}, new_env)

    def _register_all(self):
        """Register all DSL functions."""
        self._fn_registry = {
            'DELAY': self._delay,
            'TS_MEAN': self._ts_mean,
            'SMA': self._ts_mean,  # alias
            'TS_STD': self._ts_std,
            'TS_MIN': self._ts_min,
            'TS_MAX': self._ts_max,
            'TS_SUM': self._ts_sum,
            'TS_MEDIAN': self._ts_median,
            'TS_RANK': self._ts_rank,
            'TS_ZSCORE': self._ts_zscore,
            'TS_CORR': self._ts_corr,
            'TS_QUANTILE': self._ts_quantile,
            'TS_ARGMIN': self._ts_argmin,
            'TS_ARGMAX': self._ts_argmax,
            'TS_PCTCHANGE': self._ts_pctchange,
            'TS_MAD': self._ts_mad,
            'TS_SKEW': self._ts_skew,
            'DELTA': self._delta,
            'SLOPE': self._slope,
            'R_SQUARE': self._r_square,
            'RESI': self._resi,
            'RSI': self._rsi,
            'ATR': self._atr,
            'MACD': self._macd,
            'BB_UPPER': self._bb_upper,
            'BB_MIDDLE': self._bb_middle,
            'BB_LOWER': self._bb_lower,
            'WMA': self._wma,
            'ZSCORE': self._zscore,
            'RANK': self._rank,
            'ABS': np.abs,
            'LOG': np.log,
            'MIN': np.minimum,
            'MAX': np.maximum,
            'SUMIF': self._sumif,
            'COUNT': self._count,
            'REGBETA': self._regbeta,
            'PERCENTILE': self._percentile,
            'ZIGZAG_TOP_DAYS': self._zigzag_top_days,
            'ZIGZAG_BOTTOM_DAYS': self._zigzag_bottom_days,
            'ZIGZAG_TOP': self._zigzag_top,
            'ZIGZAG_BOTTOM': self._zigzag_bottom,
            'ZIGZAG_HIGHEST_TOP': self._zigzag_highest_top,
            'ZIGZAG_LOWEST_BOTTOM': self._zigzag_lowest_bottom,
            'INDUSTRY_NEUTRALIZE': self._industry_neutralize,
        }

    # === Time-series functions ===

    @staticmethod
    def _delay(arr, n=1):
        arr = np.asarray(arr, dtype=float)
        result = np.full_like(arr, np.nan)
        if n < len(arr):
            result[n:] = arr[:-n]
        return result

    @staticmethod
    def _ts_mean(arr, window=20):
        s = pd.Series(arr)
        return s.rolling(window, min_periods=1).mean().values

    @staticmethod
    def _ts_std(arr, window=20):
        s = pd.Series(arr)
        return s.rolling(window, min_periods=2).std().fillna(0).values

    @staticmethod
    def _ts_min(arr, window=20):
        s = pd.Series(arr)
        return s.rolling(window, min_periods=1).min().values

    @staticmethod
    def _ts_max(arr, window=20):
        s = pd.Series(arr)
        return s.rolling(window, min_periods=1).max().values

    @staticmethod
    def _ts_sum(arr, window=20):
        s = pd.Series(arr)
        return s.rolling(window, min_periods=1).sum().values

    @staticmethod
    def _ts_median(arr, window=20):
        s = pd.Series(arr)
        return s.rolling(window, min_periods=1).median().values

    @staticmethod
    def _ts_rank(arr, window=20):
        s = pd.Series(arr)
        return s.rolling(window, min_periods=1).apply(
            lambda x: pd.Series(x).rank().iloc[-1] / len(x), raw=False
        ).values

    @staticmethod
    def _ts_zscore(arr, window=20):
        s = pd.Series(arr)
        mean = s.rolling(window, min_periods=2).mean()
        std = s.rolling(window, min_periods=2).std()
        return ((s - mean) / (std + 1e-12)).fillna(0).values

    @staticmethod
    def _ts_corr(arr1, arr2, window=20):
        s1, s2 = pd.Series(arr1), pd.Series(arr2)
        return s1.rolling(window, min_periods=3).corr(s2).fillna(0).values

    @staticmethod
    def _ts_quantile(arr, window=20, q=0.5):
        s = pd.Series(arr)
        return s.rolling(window, min_periods=1).quantile(q).values

    @staticmethod
    def _ts_argmin(arr, window=20):
        s = pd.Series(arr)
        return s.rolling(window, min_periods=1).apply(lambda x: np.argmin(x), raw=True).values

    @staticmethod
    def _ts_argmax(arr, window=20):
        s = pd.Series(arr)
        return s.rolling(window, min_periods=1).apply(lambda x: np.argmax(x), raw=True).values

    @staticmethod
    def _ts_pctchange(arr, n=1):
        arr = np.asarray(arr, dtype=float)
        result = np.zeros_like(arr)
        result[n:] = (arr[n:] - arr[:-n]) / (np.abs(arr[:-n]) + 1e-12)
        return result

    @staticmethod
    def _ts_mad(arr, window=20):
        s = pd.Series(arr)
        return s.rolling(window, min_periods=1).apply(
            lambda x: np.median(np.abs(x - np.median(x))), raw=True
        ).values

    @staticmethod
    def _ts_skew(arr, window=20):
        s = pd.Series(arr)
        return s.rolling(window, min_periods=3).skew().fillna(0).values

    # === Derived indicators ===

    @staticmethod
    def _delta(arr, n=1):
        arr = np.asarray(arr, dtype=float)
        result = np.zeros_like(arr)
        result[n:] = arr[n:] - arr[:-n]
        return result

    @staticmethod
    def _slope(arr, window=20):
        s = pd.Series(arr)
        def _calc_slope(x):
            if len(x) < 2:
                return 0
            t = np.arange(len(x))
            return np.polyfit(t, x, 1)[0]
        return s.rolling(window, min_periods=2).apply(_calc_slope, raw=True).fillna(0).values

    @staticmethod
    def _r_square(arr, window=20):
        s = pd.Series(arr)
        def _calc_r2(x):
            if len(x) < 3:
                return 0
            t = np.arange(len(x))
            coeffs = np.polyfit(t, x, 1)
            pred = np.polyval(coeffs, t)
            ss_res = np.sum((x - pred) ** 2)
            ss_tot = np.sum((x - x.mean()) ** 2)
            return 1 - ss_res / (ss_tot + 1e-12)
        return s.rolling(window, min_periods=3).apply(_calc_r2, raw=True).fillna(0).values

    @staticmethod
    def _resi(arr, window=20):
        """Residual from linear regression."""
        s = pd.Series(arr)
        def _calc_resi(x):
            if len(x) < 3:
                return 0
            t = np.arange(len(x))
            coeffs = np.polyfit(t, x, 1)
            pred = np.polyval(coeffs, t)
            return x[-1] - pred[-1]
        return s.rolling(window, min_periods=3).apply(_calc_resi, raw=True).fillna(0).values

    @staticmethod
    def _rsi(arr, period=14):
        s = pd.Series(arr)
        delta = s.diff()
        gain = delta.where(delta > 0, 0).rolling(period, min_periods=1).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period, min_periods=1).mean()
        rs = gain / (loss + 1e-12)
        return (100 - 100 / (1 + rs)).fillna(50).values

    @staticmethod
    def _atr(high, low, close, period=14):
        h, low_values, c = np.asarray(high, float), np.asarray(low, float), np.asarray(close, float)
        prev_c = np.concatenate([[c[0]], c[:-1]])
        tr = np.maximum(
            h - low_values,
            np.maximum(np.abs(h - prev_c), np.abs(low_values - prev_c)),
        )
        return pd.Series(tr).rolling(period, min_periods=1).mean().values

    @staticmethod
    def _macd(arr, fast=12, slow=26):
        s = pd.Series(arr)
        ema_fast = s.ewm(span=fast, adjust=False).mean()
        ema_slow = s.ewm(span=slow, adjust=False).mean()
        return (ema_fast - ema_slow).values

    @staticmethod
    def _bb_upper(arr, window=20, std_mult=2):
        s = pd.Series(arr)
        mid = s.rolling(window, min_periods=1).mean()
        std = s.rolling(window, min_periods=2).std().fillna(0)
        return (mid + std_mult * std).values

    @staticmethod
    def _bb_middle(arr, window=20):
        return pd.Series(arr).rolling(window, min_periods=1).mean().values

    @staticmethod
    def _bb_lower(arr, window=20, std_mult=2):
        s = pd.Series(arr)
        mid = s.rolling(window, min_periods=1).mean()
        std = s.rolling(window, min_periods=2).std().fillna(0)
        return (mid - std_mult * std).values

    @staticmethod
    def _wma(arr, window=20):
        s = pd.Series(arr)
        weights = np.arange(1, window + 1, dtype=float)
        return s.rolling(window, min_periods=1).apply(
            lambda x: np.dot(x[-len(weights):], weights[:len(x)]) / weights[:len(x)].sum(), raw=True
        ).values

    @staticmethod
    def _zscore(arr):
        arr = np.asarray(arr, dtype=float)
        m, s = np.nanmean(arr), np.nanstd(arr)
        return (arr - m) / (s + 1e-12)

    @staticmethod
    def _rank(arr):
        return pd.Series(arr).rank(pct=True).values

    # === Conditional aggregation ===

    @staticmethod
    def _sumif(values, window, condition):
        """Sum values where condition is true over window."""
        v = np.asarray(values, dtype=float)
        c = np.asarray(condition, dtype=bool)
        masked = np.where(c, v, 0.0)
        return pd.Series(masked).rolling(window, min_periods=1).sum().values

    @staticmethod
    def _count(condition, window):
        c = np.asarray(condition, dtype=float)
        return pd.Series(c).rolling(window, min_periods=1).sum().values

    # === Regression ===

    @staticmethod
    def _regbeta(y, x, window=60):
        sy, sx = pd.Series(y), pd.Series(x)
        def _beta(args):
            yy, xx = args[:len(args)//2], args[len(args)//2:]
            if len(yy) < 3:
                return 0
            cov = np.cov(yy, xx)[0, 1]
            var = np.var(xx)
            return cov / (var + 1e-12)
        combined = pd.concat([sy, sx], axis=1)
        return combined.rolling(window, min_periods=3).apply(
            lambda x: np.polyfit(np.arange(len(x)), x, 1)[0], raw=True
        ).iloc[:, 0].fillna(0).values

    @staticmethod
    def _percentile(arr, q):
        return np.percentile(arr, q * 100)

    # === Zigzag functions (simplified) ===

    @staticmethod
    def _zigzag_top_days(arr, threshold=1):
        """Days since last swing high."""
        arr = np.asarray(arr, dtype=float)
        n = len(arr)
        result = np.zeros(n)
        last_top = 0
        for i in range(2, n):
            if arr[i-1] > arr[i-2] and arr[i-1] >= arr[i]:
                last_top = i - 1
            result[i] = i - last_top if last_top > 0 else i
        return result

    @staticmethod
    def _zigzag_bottom_days(arr, threshold=1):
        """Days since last swing low."""
        arr = np.asarray(arr, dtype=float)
        n = len(arr)
        result = np.zeros(n)
        last_bottom = 0
        for i in range(2, n):
            if arr[i-1] < arr[i-2] and arr[i-1] <= arr[i]:
                last_bottom = i - 1
            result[i] = i - last_bottom if last_bottom > 0 else i
        return result

    @staticmethod
    def _zigzag_top(arr, threshold=1):
        """Price at last swing high."""
        arr = np.asarray(arr, dtype=float)
        n = len(arr)
        result = np.full(n, arr[0])
        for i in range(2, n):
            if arr[i-1] > arr[i-2] and arr[i-1] >= arr[i]:
                result[i] = arr[i-1]
            else:
                result[i] = result[i-1]
        return result

    @staticmethod
    def _zigzag_bottom(arr, threshold=1, pct=None):
        """Price at last swing low."""
        arr = np.asarray(arr, dtype=float)
        n = len(arr)
        result = np.full(n, arr[0])
        for i in range(2, n):
            if arr[i-1] < arr[i-2] and arr[i-1] <= arr[i]:
                result[i] = arr[i-1]
            else:
                result[i] = result[i-1]
        return result

    @staticmethod
    def _zigzag_highest_top(arr, window=30):
        """Highest swing top in window."""
        arr = np.asarray(arr, dtype=float)
        return pd.Series(arr).rolling(window, min_periods=1).max().values

    @staticmethod
    def _zigzag_lowest_bottom(arr, window=30):
        """Lowest swing bottom in window."""
        arr = np.asarray(arr, dtype=float)
        return pd.Series(arr).rolling(window, min_periods=1).min().values

    @staticmethod
    def _industry_neutralize(arr, industry):
        """Industry neutralization (simplified: demean)."""
        arr = np.asarray(arr, dtype=float)
        return arr - np.nanmean(arr)
