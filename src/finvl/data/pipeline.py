"""Tri-modal data processing pipeline for FinVL-MAS."""

from __future__ import annotations

import logging
import os
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from finvl.data.schema import (
    BoundingBox,
    ChartImageData,
    DecisionSample,
    FactorAlignment,
    FinVLDataset,
    TextualContext,
    TimeSeriesData,
    validate_ohlcv_df,
)

logger = logging.getLogger(__name__)


def fetch_ohlcv_yfinance(ticker: str, start: str, end: str, save_path: Optional[str] = None) -> pd.DataFrame:
    try:
        import yfinance as yf
    except ImportError as exc:
        raise ImportError("Install yfinance: pip install yfinance") from exc

    df = yf.download(ticker, start=start, end=end, auto_adjust=False, progress=False)
    if df.empty:
        raise ValueError(f"No data returned for {ticker}")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    df = df.rename(columns=str.lower)
    df.index.name = "date"
    if save_path:
        os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
        df.to_csv(save_path)
    return validate_ohlcv_df(df)


def load_ohlcv_csv(path: str) -> pd.DataFrame:
    return validate_ohlcv_df(pd.read_csv(path))


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    c = out["close"]
    out["sma_5"] = c.rolling(5, min_periods=1).mean()
    out["sma_20"] = c.rolling(20, min_periods=1).mean()

    delta = c.diff()
    gain = delta.clip(lower=0).rolling(14, min_periods=1).mean()
    loss = (-delta.clip(upper=0)).rolling(14, min_periods=1).mean()
    rs = gain / loss.replace(0, np.nan)
    out["rsi_14"] = (100 - (100 / (1 + rs))).fillna(50)

    ema12 = c.ewm(span=12, adjust=False).mean()
    ema26 = c.ewm(span=26, adjust=False).mean()
    out["macd"] = ema12 - ema26
    out["macd_signal"] = out["macd"].ewm(span=9, adjust=False).mean()

    std20 = c.rolling(20, min_periods=1).std().fillna(0)
    out["bb_upper"] = out["sma_20"] + 2 * std20
    out["bb_lower"] = out["sma_20"] - 2 * std20

    tr = pd.concat(
        [out["high"] - out["low"], (out["high"] - c.shift(1)).abs(), (out["low"] - c.shift(1)).abs()],
        axis=1,
    ).max(axis=1)
    out["atr_14"] = tr.rolling(14, min_periods=1).mean()
    out["daily_returns"] = c.pct_change().fillna(0)
    return out


def _clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(v, hi))


def _price_to_y(price: float, price_min: float, price_max: float, height: int) -> int:
    if price_max - price_min < 1e-12:
        return height // 2
    ratio = (price - price_min) / (price_max - price_min)
    return int((1.0 - ratio) * (height * 0.72))


def _build_factor_bboxes(df_window: pd.DataFrame, width: int, height: int) -> Tuple[List[BoundingBox], List[FactorAlignment]]:
    if len(df_window) == 0:
        return [], []

    low = float(df_window["low"].min())
    high = float(df_window["high"].max())
    n = len(df_window)

    def bar_x(idx: int) -> int:
        return int((idx / max(1, n - 1)) * (width * 0.9) + width * 0.05)

    boxes: List[BoundingBox] = []
    aligns: List[FactorAlignment] = []

    last_20 = df_window.iloc[-min(20, n) :]
    trend_score = (float(last_20["close"].iloc[-1]) - float(last_20["close"].iloc[0])) / max(1e-6, float(last_20["close"].iloc[0]))
    boxes.append(
        BoundingBox(
            x0=bar_x(max(0, n - len(last_20))),
            y0=_price_to_y(float(last_20["high"].max()), low, high, height),
            x1=bar_x(n - 1),
            y1=_price_to_y(float(last_20["low"].min()), low, high, height),
            label="trend_zone",
            confidence=0.85,
        )
    )
    b = boxes[-1]
    b.y0, b.y1 = min(b.y0, b.y1), max(b.y0, b.y1)
    aligns.append(FactorAlignment("trend_strength", "Trend Strength", float(np.tanh(trend_score * 8.0)), "trend_zone", "Last 20 bars slope and drift"))

    atr = float(df_window["atr_14"].iloc[-1]) if "atr_14" in df_window.columns else 0.0
    close = float(df_window["close"].iloc[-1])
    vol_score = atr / max(close, 1e-6)
    cy = _price_to_y(close, low, high, height)
    boxes.append(BoundingBox(bar_x(max(0, n - 14)), _clamp(cy - int(height * 0.06), 0, height - 1), bar_x(n - 1), _clamp(cy + int(height * 0.06), 0, height - 1), "volatility_zone", 0.80))
    aligns.append(FactorAlignment("volatility_cluster", "Volatility Cluster", float(np.tanh(vol_score * 20.0)), "volatility_zone", "ATR-normalized local swings"))

    mom = float(df_window["daily_returns"].tail(5).mean()) if "daily_returns" in df_window.columns else 0.0
    boxes.append(BoundingBox(bar_x(max(0, n - 5)), int(height * 0.75), bar_x(n - 1), int(height * 0.90), "momentum_zone", 0.75))
    aligns.append(FactorAlignment("momentum_5d", "Momentum (5d)", float(np.tanh(mom * 50.0)), "momentum_zone", "Mean return over 5 bars"))

    vol = df_window["volume"].tail(20)
    spike = float(vol.iloc[-1] / max(vol.mean(), 1e-6) - 1.0)
    boxes.append(BoundingBox(bar_x(max(0, n - 2)), int(height * 0.82), bar_x(n - 1), int(height * 0.98), "volume_spike_zone", 0.78))
    aligns.append(FactorAlignment("volume_spike", "Volume Spike", float(np.tanh(spike)), "volume_spike_zone", "Latest volume vs 20-bar mean"))

    return boxes, aligns


def render_chart_for_sample(
    df_window: pd.DataFrame,
    asset: str,
    decision_date: str,
    output_dir: str,
    chart_type: str = "candlestick_volume",
    overlays: Optional[List[str]] = None,
    dpi: int = 150,
    figsize: tuple = (10.24, 7.68),
    enable_factor_bbox: bool = True,
) -> ChartImageData:
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
        kwargs = dict(type="candle", volume=True, style="charles", figsize=figsize, savefig=dict(fname=image_path, dpi=dpi, bbox_inches="tight"), warn_too_much_data=500)
        if addplots:
            kwargs["addplot"] = addplots
        mpf.plot(df_window, **kwargs)
        plt.close("all")
    except Exception:
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=figsize, gridspec_kw={"height_ratios": [3, 1]}, sharex=True)
        x = np.arange(len(df_window))
        colors = ["#26a69a" if c >= o else "#ef5350" for o, c in zip(df_window["open"], df_window["close"])]
        ax1.bar(x, df_window["high"] - df_window["low"], bottom=df_window["low"], width=0.1, color=colors)
        ax1.bar(x, (df_window["close"] - df_window["open"]).abs(), bottom=df_window[["open", "close"]].min(axis=1), width=0.6, color=colors)
        ax2.bar(x, df_window["volume"], color=colors, alpha=0.6)
        plt.tight_layout()
        fig.savefig(image_path, dpi=dpi, bbox_inches="tight")
        plt.close(fig)

    width = int(figsize[0] * dpi)
    height = int(figsize[1] * dpi)
    bboxes, aligns = ([], [])
    if enable_factor_bbox:
        bboxes, aligns = _build_factor_bboxes(df_window, width=width, height=height)

    return ChartImageData(
        image_path=fname,
        chart_type=chart_type,
        lookback_bars=len(df_window),
        overlays=overlays,
        width=width,
        height=height,
        dpi=dpi,
        price_min=float(df_window["low"].min()),
        price_max=float(df_window["high"].max()),
        date_start=df_window.index[0].strftime("%Y-%m-%d"),
        date_end=df_window.index[-1].strftime("%Y-%m-%d"),
        bboxes=bboxes,
        factor_alignments=aligns,
    )


def build_time_series_data(df_window: pd.DataFrame) -> TimeSeriesData:
    def _safe_list(col: str) -> Optional[List[float]]:
        if col in df_window.columns:
            return [round(float(v), 6) if not np.isnan(v) else None for v in df_window[col].values]
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


def compute_labels(df_full: pd.DataFrame, decision_date: str, horizons: Sequence[int] = (1, 3, 5)) -> Dict[str, Any]:
    dt = pd.Timestamp(decision_date)
    future = df_full.loc[df_full.index > dt]
    if len(future) == 0:
        return {"forward_return_1d": None, "direction": None}

    close_today = float(df_full.loc[df_full.index <= dt, "close"].iloc[-1])
    labels: Dict[str, Any] = {}
    for h in horizons:
        if len(future) >= h:
            future_close = float(future["close"].iloc[h - 1])
            labels[f"forward_return_{h}d"] = round((future_close - close_today) / close_today, 6)
        else:
            labels[f"forward_return_{h}d"] = None

    ret_1d = labels.get("forward_return_1d")
    if ret_1d is not None:
        labels["direction"] = "up" if ret_1d > 0.005 else "down" if ret_1d < -0.005 else "flat"
    else:
        labels["direction"] = None
    return labels


def build_dataset(
    ohlcv_df: pd.DataFrame,
    asset: str,
    decision_dates: List[str],
    chart_output_dir: str,
    lookback: int = 60,
    market: str = "",
    text_provider: Optional[Callable[[str, str], TextualContext]] = None,
    chart_overlays: Optional[List[str]] = None,
    split: str = "",
    enable_factor_bbox: bool = True,
) -> FinVLDataset:
    df_full = compute_indicators(ohlcv_df)
    samples: List[DecisionSample] = []
    chart_overlays = chart_overlays or ["sma_5", "sma_20"]

    for date_str in decision_dates:
        available = df_full.loc[df_full.index <= pd.Timestamp(date_str)]
        if len(available) < max(20, lookback // 3):
            continue
        window = available.iloc[-lookback:]

        ts_data = build_time_series_data(window)
        chart_data = render_chart_for_sample(window, asset, date_str, chart_output_dir, overlays=chart_overlays, enable_factor_bbox=enable_factor_bbox)
        text_data = text_provider(asset, date_str) if text_provider else TextualContext()
        labels = compute_labels(df_full, date_str)

        samples.append(
            DecisionSample(
                sample_id=f"{asset}_{date_str}",
                alignment_id=f"{asset}_{date_str}_{lookback}",
                split=split,
                asset=asset,
                decision_date=date_str,
                time_series=ts_data,
                chart_image=chart_data,
                textual_context=text_data,
                label=labels,
                market=market,
                lookback_window=lookback,
                metadata={"bbox_count": len(chart_data.bboxes), "factor_alignment_count": len(chart_data.factor_alignments), "text_available": text_data.has_text},
            )
        )

    logger.info("Built %d samples for %s", len(samples), asset)
    return FinVLDataset(
        samples=samples,
        split=split,
        market=market,
        assets=[asset],
        date_range=(decision_dates[0], decision_dates[-1]) if decision_dates else ("", ""),
        metadata={"lookback": lookback, "has_bbox_supervision": enable_factor_bbox},
    )
