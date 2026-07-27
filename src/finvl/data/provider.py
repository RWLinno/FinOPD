"""
Data providers for FinVL-MAS.
Loads OHLCV data from CSV files with proper validation and temporal slicing.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from .schema import validate_ohlcv_df

logger = logging.getLogger(__name__)


class OHLCVProvider:
    """
    Provides OHLCV data with point-in-time guarantees.
    Only returns data up to and including the requested date.
    """

    def __init__(self, data_path: str):
        path = Path(data_path)
        if not path.exists():
            raise FileNotFoundError(f"Data file not found: {data_path}")

        raw = pd.read_csv(path)
        self.df = validate_ohlcv_df(raw)
        logger.info(
            f"Loaded {len(self.df)} bars from {data_path} "
            f"({self.df.index.min():%Y-%m-%d} to {self.df.index.max():%Y-%m-%d})"
        )

    def _asset_frame(self, asset: Optional[str] = None) -> pd.DataFrame:
        if "ticker" not in self.df.columns:
            return self.df
        if asset is None:
            tickers = self.df["ticker"].dropna().unique()
            if len(tickers) > 1:
                raise ValueError("multi-asset data requires an explicit asset")
            return self.df
        selected = self.df[self.df["ticker"] == asset]
        if selected.empty:
            raise ValueError(f"asset not found: {asset}")
        return selected

    def get_window(
        self,
        end_date: str,
        lookback: int = 60,
        start_date: Optional[str] = None,
        asset: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Return OHLCV data up to `end_date` (inclusive) with `lookback` bars.
        Guarantees no future data leakage.
        """
        end_ts = pd.Timestamp(end_date)
        frame = self._asset_frame(asset)
        mask = frame.index <= end_ts
        available = frame.loc[mask]

        if start_date is not None:
            start_ts = pd.Timestamp(start_date)
            available = available.loc[available.index >= start_ts]

        if len(available) == 0:
            raise ValueError(f"No data available up to {end_date}")

        return available.iloc[-lookback:].copy()

    def get_date_range(
        self, start_date: str, end_date: str, asset: Optional[str] = None
    ) -> pd.DataFrame:
        """Return OHLCV data for a date range (inclusive)."""
        s = pd.Timestamp(start_date)
        e = pd.Timestamp(end_date)
        frame = self._asset_frame(asset)
        return frame.loc[(frame.index >= s) & (frame.index <= e)].copy()

    def trading_dates(
        self, start_date: str, end_date: str, asset: Optional[str] = None
    ) -> list[str]:
        """Return list of trading date strings in range."""
        sub = self.get_date_range(start_date, end_date, asset=asset)
        return [d.strftime("%Y-%m-%d") for d in sub.index]

    @property
    def date_range(self) -> tuple[str, str]:
        return (
            self.df.index.min().strftime("%Y-%m-%d"),
            self.df.index.max().strftime("%Y-%m-%d"),
        )
