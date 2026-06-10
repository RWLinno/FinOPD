"""
Data providers for FinVL-MAS.
Loads OHLCV data from CSV files with proper validation and temporal slicing.
Supports both single-ticker and multi-ticker CSV formats.
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

    Supports two modes:
    - Single-ticker CSV (no 'ticker' column): all rows belong to one asset.
    - Multi-ticker CSV (has 'ticker' column): pass ticker= to filter.
    """

    def __init__(self, data_path: str, ticker: Optional[str] = None):
        path = Path(data_path)
        if not path.exists():
            raise FileNotFoundError(f"Data file not found: {data_path}")

        raw = pd.read_csv(path)
        col_lower = {c.lower(): c for c in raw.columns}

        # Detect multi-ticker CSV and filter if ticker is specified
        ticker_col = col_lower.get("ticker")
        if ticker_col and ticker is not None:
            raw = raw[raw[ticker_col] == ticker].copy()
            if len(raw) == 0:
                raise ValueError(
                    f"No data for ticker '{ticker}' in {data_path}"
                )
            raw = raw.drop(columns=[ticker_col])
            logger.info(f"Filtered ticker={ticker}, {len(raw)} bars")

        # Also drop 'adj close' / 'adj_close' if present (not needed)
        for col_name in ["adj close", "adj_close"]:
            real_name = col_lower.get(col_name.replace(" ", "").lower())
            # Try exact match
            if col_name in raw.columns:
                raw = raw.drop(columns=[col_name])
            elif col_name.replace(" ", "_") in raw.columns:
                raw = raw.drop(columns=[col_name.replace(" ", "_")])

        self.df = validate_ohlcv_df(raw)
        self._ticker = ticker
        logger.info(
            f"Loaded {len(self.df)} bars from {data_path} "
            f"({self.df.index.min():%Y-%m-%d} to {self.df.index.max():%Y-%m-%d})"
            + (f" [ticker={ticker}]" if ticker else "")
        )

    @property
    def ticker(self) -> Optional[str]:
        return self._ticker

    def get_window(
        self,
        end_date: str,
        lookback: int = 60,
        start_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Return OHLCV data up to `end_date` (inclusive) with `lookback` bars.
        Guarantees no future data leakage.
        """
        end_ts = pd.Timestamp(end_date)
        mask = self.df.index <= end_ts
        available = self.df.loc[mask]

        if start_date is not None:
            start_ts = pd.Timestamp(start_date)
            available = available.loc[available.index >= start_ts]

        if len(available) == 0:
            raise ValueError(f"No data available up to {end_date}")

        return available.iloc[-lookback:].copy()

    def get_date_range(self, start_date: str, end_date: str) -> pd.DataFrame:
        """Return OHLCV data for a date range (inclusive)."""
        s = pd.Timestamp(start_date)
        e = pd.Timestamp(end_date)
        return self.df.loc[(self.df.index >= s) & (self.df.index <= e)].copy()

    def trading_dates(self, start_date: str, end_date: str) -> list[str]:
        """Return list of trading date strings in range."""
        sub = self.get_date_range(start_date, end_date)
        return [d.strftime("%Y-%m-%d") for d in sub.index]

    @property
    def date_range(self) -> tuple[str, str]:
        return (
            self.df.index.min().strftime("%Y-%m-%d"),
            self.df.index.max().strftime("%Y-%m-%d"),
        )
