"""
Financial chart renderer for FinVL-MAS.
Produces candlestick + volume charts with configurable overlays
using mplfinance and matplotlib.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from finvl.core.types import ChartMetadata

logger = logging.getLogger(__name__)

# Attempt mplfinance; fall back to pure matplotlib
try:
    import mplfinance as mpf
    HAS_MPF = True
except ImportError:
    HAS_MPF = False
    logger.warning("mplfinance not installed; falling back to matplotlib candlestick rendering")


class ChartRenderer:
    """Renders financial OHLCV data as chart images."""

    def __init__(self, config: Dict[str, Any] | None = None):
        config = config or {}
        self.image_width = config.get("image_size", [1024, 768])[0]
        self.image_height = config.get("image_size", [1024, 768])[1]
        self.dpi = config.get("dpi", 150)
        self.style = config.get("style", "charles")
        self.output_dir = config.get("output_dir", "data/charts")
        os.makedirs(self.output_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def render_candlestick(
        self,
        df: pd.DataFrame,
        asset: str = "ASSET",
        overlays: Optional[List[Dict[str, Any]]] = None,
        save_path: Optional[str] = None,
    ) -> Tuple[str, ChartMetadata]:
        """
        Render a candlestick + volume chart.

        Args:
            df: OHLCV DataFrame with DatetimeIndex.
            asset: Asset name for title.
            overlays: List of overlay dicts, e.g. [{"type": "sma", "periods": [5,20]}].
            save_path: Optional explicit output path.

        Returns:
            (image_path, ChartMetadata)
        """
        if save_path is None:
            start = df.index[0].strftime("%Y%m%d")
            end = df.index[-1].strftime("%Y%m%d")
            save_path = os.path.join(self.output_dir, f"{asset}_{start}_{end}.png")

        overlay_plots = self._build_overlays(df, overlays or [])

        if HAS_MPF:
            self._render_mpf(df, asset, overlay_plots, save_path)
        else:
            self._render_matplotlib(df, asset, overlay_plots, save_path)

        meta = ChartMetadata(
            image_path=save_path,
            asset=asset,
            start_date=df.index[0].strftime("%Y-%m-%d"),
            end_date=df.index[-1].strftime("%Y-%m-%d"),
            timeframe="daily",
            price_min=float(df["low"].min()),
            price_max=float(df["high"].max()),
            current_price=float(df["close"].iloc[-1]),
            overlays=[str(o) for o in (overlays or [])],
        )
        return save_path, meta

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_overlays(
        self, df: pd.DataFrame, overlays: List[Dict[str, Any]]
    ) -> List[Any]:
        """Build mplfinance-compatible addplot list."""
        plots = []
        for ov in overlays:
            ov_type = ov.get("type", "")
            if ov_type == "sma":
                for p in ov.get("periods", [20]):
                    sma = df["close"].rolling(window=p, min_periods=1).mean()
                    if HAS_MPF:
                        plots.append(mpf.make_addplot(sma, width=0.8))
                    else:
                        plots.append(("sma", sma, p))
            elif ov_type == "bollinger":
                period = ov.get("period", 20)
                std = ov.get("std", 2)
                mid = df["close"].rolling(window=period, min_periods=1).mean()
                roll_std = df["close"].rolling(window=period, min_periods=1).std().fillna(0)
                upper = mid + std * roll_std
                lower = mid - std * roll_std
                if HAS_MPF:
                    plots.append(mpf.make_addplot(upper, width=0.6, linestyle="--"))
                    plots.append(mpf.make_addplot(lower, width=0.6, linestyle="--"))
                else:
                    plots.append(("bb_upper", upper, period))
                    plots.append(("bb_lower", lower, period))
        return plots

    def _render_mpf(
        self,
        df: pd.DataFrame,
        asset: str,
        addplots: list,
        save_path: str,
    ):
        figsize = (self.image_width / self.dpi, self.image_height / self.dpi)
        kwargs: Dict[str, Any] = {
            "type": "candle",
            "volume": True,
            "title": f"{asset}",
            "style": self.style,
            "figsize": figsize,
            "savefig": {"fname": save_path, "dpi": self.dpi, "bbox_inches": "tight"},
            "warn_too_much_data": 500,
        }
        if addplots:
            kwargs["addplot"] = addplots
        mpf.plot(df, **kwargs)
        plt.close("all")

    def _render_matplotlib(
        self,
        df: pd.DataFrame,
        asset: str,
        overlay_data: list,
        save_path: str,
    ):
        """Fallback candlestick rendering without mplfinance."""
        fig, (ax1, ax2) = plt.subplots(
            2, 1, figsize=(self.image_width / self.dpi, self.image_height / self.dpi),
            gridspec_kw={"height_ratios": [3, 1]}, sharex=True,
        )
        dates = np.arange(len(df))
        colors = ["green" if c >= o else "red" for o, c in zip(df["open"], df["close"])]

        ax1.bar(dates, df["high"] - df["low"], bottom=df["low"], width=0.1, color=colors)
        ax1.bar(
            dates,
            (df["close"] - df["open"]).abs(),
            bottom=df[["open", "close"]].min(axis=1),
            width=0.6, color=colors,
        )
        ax1.set_title(asset)
        ax1.set_ylabel("Price")

        for item in overlay_data:
            name, series, param = item
            ax1.plot(dates, series.values, linewidth=0.7, label=f"{name}({param})")
        if overlay_data:
            ax1.legend(fontsize=6)

        ax2.bar(dates, df["volume"], color=colors, alpha=0.7)
        ax2.set_ylabel("Volume")

        plt.tight_layout()
        fig.savefig(save_path, dpi=self.dpi, bbox_inches="tight")
        plt.close(fig)
