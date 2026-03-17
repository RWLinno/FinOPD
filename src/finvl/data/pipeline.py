"""
Tri-modal data processing pipeline for FinVL-MAS.

Builds aligned DecisionSample records from raw data sources:
  1. OHLCV price data (yfinance or CSV)
  2. Chart images (rendered from OHLCV)
  3. Textual context (news/filings, or synthetic for testing)

Output: JSONL file + chart image directory, ready for experiments.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from finvl.data.schema import (
    ChartImageData,
    DecisionSample,
    FinVLDataset,
    NewsItem,
    TextualContext,
    TimeSeriesData,
    validate_ohlcv_df,
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# OHLCV Data Fetching
# ──────────────────────────────────────────────

def fetch_ohlcv_yfinance(
    ticker: str,
    start: str,
    end: str,
    save_path: Optional[str] = None,
) -> pd.DataFrame:
    """Download OHLCV data from Yahoo Finance via yfinance."""
    try:
        import yfinance as yf
    except ImportError:
        raise ImportError("Install yfinance: pip install yfinance")

    logger.info(f"Downloading {ticker} from {start} to {end}...")
    df = yf.download(ticker, start=start, end=end, auto_adjust=False, progress=False)
    if df.empty:
        raise ValueError(f"No data returned for {ticker}")

    # Flatten MultiIndex columns if present
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]

    df = df.rename(columns=str.lower)
    df.index.name = "date"

    if save_path:
        os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
        df.to_csv(save_path)
        logger.info(f"Saved {len(df)} bars to {save_path}")

    return validate_ohlcv_df(df)


def load_ohlcv_csv(path: str) -> pd.DataFrame:
    """Load OHLCV data from a CSV file."""
    df = pd.read_csv(path)
    return validate_ohlcv_df(df)


# ──────────────────────────────────────────────
# Technical Indicators
# ──────────────────────────────────────────────

def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Compute standard technical indicators on OHLCV DataFrame."""
    out = df.copy()
    c = out["close"]

    # Simple Moving Averages
    out["sma_5"] = c.rolling(5, min_periods=1).mean()
    out["sma_20"] = c.rolling(20, min_periods=1).mean()

    # RSI (14)
    delta = c.diff()
    gain = delta.clip(lower=0).rolling(14, min_periods=1).mean()
    loss = (-delta.clip(upper=0)).rolling(14, min_periods=1).mean()
    rs = gain / loss.replace(0, np.nan)
    out["rsi_14"] = 100 - (100 / (1 + rs))
    out["rsi_14"] = out["rsi_14"].fillna(50)

    # MACD
    ema12 = c.ewm(span=12, adjust=False).mean()
    ema26 = c.ewm(span=26, adjust=False).mean()
    out["macd"] = ema12 - ema26
    out["macd_signal"] = out["macd"].ewm(span=9, adjust=False).mean()

    # Bollinger Bands
    sma20 = out["sma_20"]
    std20 = c.rolling(20, min_periods=1).std().fillna(0)
    out["bb_upper"] = sma20 + 2 * std20
    out["bb_lower"] = sma20 - 2 * std20

    # ATR (14)
    h, l = out["high"], out["low"]
    prev_c = c.shift(1)
    tr = pd.concat([
        h - l,
        (h - prev_c).abs(),
        (l - prev_c).abs(),
    ], axis=1).max(axis=1)
    out["atr_14"] = tr.rolling(14, min_periods=1).mean()

    # Daily returns
    out["daily_returns"] = c.pct_change().fillna(0)

    return out


# ──────────────────────────────────────────────
# Chart Rendering
# ──────────────────────────────────────────────

def render_chart_for_sample(
    df_window: pd.DataFrame,
    asset: str,
    decision_date: str,
    output_dir: str,
    chart_type: str = "candlestick_volume",
    overlays: Optional[List[str]] = None,
    dpi: int = 150,
    figsize: tuple = (10.24, 7.68),
) -> ChartImageData:
    """Render a chart image for a decision sample and return metadata."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    overlays = overlays or ["sma_5", "sma_20"]
    fname = f"{asset}_{decision_date}.png"
    image_path = os.path.join(output_dir, fname)
    os.makedirs(output_dir, exist_ok=True)

    try:
        import mplfinance as mpf
        addplots = []
        if "sma_5" in overlays and "sma_5" in df_window.columns:
            addplots.append(mpf.make_addplot(df_window["sma_5"], width=0.8, color="#2196f3"))
        if "sma_20" in overlays and "sma_20" in df_window.columns:
            addplots.append(mpf.make_addplot(df_window["sma_20"], width=0.8, color="#ff9800"))
        if "bb_upper" in overlays and "bb_upper" in df_window.columns:
            addplots.append(mpf.make_addplot(df_window["bb_upper"], width=0.6, linestyle="--", color="#9e9e9e"))
            addplots.append(mpf.make_addplot(df_window["bb_lower"], width=0.6, linestyle="--", color="#9e9e9e"))

        kwargs = dict(
            type="candle", volume=True, style="charles",
            figsize=figsize, savefig=dict(fname=image_path, dpi=dpi, bbox_inches="tight"),
            warn_too_much_data=500,
        )
        if addplots:
            kwargs["addplot"] = addplots
        mpf.plot(df_window, **kwargs)
        plt.close("all")
    except Exception:
        # Fallback to basic matplotlib
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=figsize,
                                        gridspec_kw={"height_ratios": [3, 1]}, sharex=True)
        x = np.arange(len(df_window))
        colors = ["#26a69a" if c >= o else "#ef5350"
                  for o, c in zip(df_window["open"], df_window["close"])]
        ax1.bar(x, df_window["high"] - df_window["low"], bottom=df_window["low"], width=0.1, color=colors)
        ax1.bar(x, (df_window["close"] - df_window["open"]).abs(),
                bottom=df_window[["open", "close"]].min(axis=1), width=0.6, color=colors)
        ax1.set_ylabel("Price")
        ax1.set_title(f"{asset} — {decision_date}")
        ax2.bar(x, df_window["volume"], color=colors, alpha=0.6)
        ax2.set_ylabel("Volume")
        plt.tight_layout()
        fig.savefig(image_path, dpi=dpi, bbox_inches="tight")
        plt.close(fig)

    return ChartImageData(
        image_path=fname,
        chart_type=chart_type,
        lookback_bars=len(df_window),
        overlays=overlays,
        width=int(figsize[0] * dpi),
        height=int(figsize[1] * dpi),
        dpi=dpi,
        price_min=float(df_window["low"].min()),
        price_max=float(df_window["high"].max()),
        date_start=df_window.index[0].strftime("%Y-%m-%d"),
        date_end=df_window.index[-1].strftime("%Y-%m-%d"),
    )


# ──────────────────────────────────────────────
# Time-Series Window Builder
# ──────────────────────────────────────────────

def build_time_series_data(df_window: pd.DataFrame) -> TimeSeriesData:
    """Build a TimeSeriesData object from a DataFrame window with indicators."""
    def _safe_list(col: str) -> Optional[List[float]]:
        if col in df_window.columns:
            return [round(float(v), 6) if not np.isnan(v) else None
                    for v in df_window[col].values]
        return None

    return TimeSeriesData(
        dates=[d.strftime("%Y-%m-%d") for d in df_window.index],
        open=[round(float(v), 4) for v in df_window["open"]],
        high=[round(float(v), 4) for v in df_window["high"]],
        low=[round(float(v), 4) for v in df_window["low"]],
        close=[round(float(v), 4) for v in df_window["close"]],
        volume=[round(float(v), 2) for v in df_window["volume"]],
        sma_5=_safe_list("sma_5"),
        sma_20=_safe_list("sma_20"),
        rsi_14=_safe_list("rsi_14"),
        macd=_safe_list("macd"),
        macd_signal=_safe_list("macd_signal"),
        bb_upper=_safe_list("bb_upper"),
        bb_lower=_safe_list("bb_lower"),
        atr_14=_safe_list("atr_14"),
        daily_returns=_safe_list("daily_returns"),
    )


# ──────────────────────────────────────────────
# Label Computation
# ──────────────────────────────────────────────

def compute_labels(
    df_full: pd.DataFrame,
    decision_date: str,
    horizons: Sequence[int] = (1, 3, 5),
) -> Dict[str, Any]:
    """
    Compute forward-looking labels for a decision date.
    Only uses data AFTER decision_date (no leakage).
    """
    dt = pd.Timestamp(decision_date)
    future = df_full.loc[df_full.index > dt]
    if len(future) == 0:
        return {"forward_return_1d": None, "direction": None}

    close_today = float(df_full.loc[df_full.index <= dt, "close"].iloc[-1])
    labels: Dict[str, Any] = {}

    for h in horizons:
        if len(future) >= h:
            future_close = float(future["close"].iloc[h - 1])
            ret = (future_close - close_today) / close_today
            labels[f"forward_return_{h}d"] = round(ret, 6)
        else:
            labels[f"forward_return_{h}d"] = None

    ret_1d = labels.get("forward_return_1d")
    if ret_1d is not None:
        if ret_1d > 0.005:
            labels["direction"] = "up"
        elif ret_1d < -0.005:
            labels["direction"] = "down"
        else:
            labels["direction"] = "flat"
    else:
        labels["direction"] = None

    return labels


# ──────────────────────────────────────────────
# Full Pipeline: Build Aligned Dataset
# ──────────────────────────────────────────────

def build_dataset(
    ohlcv_df: pd.DataFrame,
    asset: str,
    decision_dates: List[str],
    chart_output_dir: str,
    lookback: int = 60,
    market: str = "",
    text_provider=None,  # Optional callable(asset, date) -> TextualContext
    chart_overlays: Optional[List[str]] = None,
) -> FinVLDataset:
    """
    Build a tri-modal aligned dataset from OHLCV data.

    Args:
        ohlcv_df: Full OHLCV DataFrame (already validated).
        asset: Asset ticker/name.
        decision_dates: List of date strings for which to build samples.
        chart_output_dir: Directory to save rendered chart images.
        lookback: Number of bars for the lookback window.
        market: Market identifier (e.g., "US", "CN").
        text_provider: Optional function returning TextualContext for (asset, date).
        chart_overlays: Overlays for chart rendering.

    Returns:
        FinVLDataset with aligned samples.
    """
    # Pre-compute indicators on full dataframe
    df_full = compute_indicators(ohlcv_df)

    samples: List[DecisionSample] = []
    chart_overlays = chart_overlays or ["sma_5", "sma_20"]

    for date_str in decision_dates:
        dt = pd.Timestamp(date_str)

        # Get lookback window (point-in-time, no leakage)
        mask = df_full.index <= dt
        available = df_full.loc[mask]
        if len(available) < max(20, lookback // 3):
            logger.debug(f"Skipping {date_str}: insufficient history ({len(available)} bars)")
            continue

        window = available.iloc[-lookback:]

        # Modality 1: Time-series
        ts_data = build_time_series_data(window)

        # Modality 2: Chart image
        chart_data = render_chart_for_sample(
            df_window=window, asset=asset, decision_date=date_str,
            output_dir=chart_output_dir, overlays=chart_overlays,
        )

        # Modality 3: Textual context
        if text_provider is not None:
            text_data = text_provider(asset, date_str)
        else:
            text_data = TextualContext()

        # Labels
        labels = compute_labels(df_full, date_str)

        sample = DecisionSample(
            sample_id=f"{asset}_{date_str}",
            asset=asset,
            decision_date=date_str,
            time_series=ts_data,
            chart_image=chart_data,
            textual_context=text_data,
            label=labels,
            market=market,
            lookback_window=lookback,
        )
        samples.append(sample)

    logger.info(f"Built {len(samples)} samples for {asset}")

    return FinVLDataset(
        samples=samples,
        market=market,
        assets=[asset],
        date_range=(decision_dates[0], decision_dates[-1]) if decision_dates else ("", ""),
    )
