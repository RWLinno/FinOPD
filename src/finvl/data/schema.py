"""
Data schemas for FinVL-MAS.
Defines tri-modal aligned data structures: chart images, text, and time-series.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


@dataclass
class OHLCVBar:
    """Single OHLCV bar."""

    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    adj_close: Optional[float] = None


@dataclass
class TimeSeriesData:
    """Multivariate time-series data for a lookback window."""

    dates: List[str]
    open: List[float]
    high: List[float]
    low: List[float]
    close: List[float]
    volume: List[float]
    sma_5: Optional[List[float]] = None
    sma_20: Optional[List[float]] = None
    rsi_14: Optional[List[float]] = None
    macd: Optional[List[float]] = None
    macd_signal: Optional[List[float]] = None
    bb_upper: Optional[List[float]] = None
    bb_lower: Optional[List[float]] = None
    atr_14: Optional[List[float]] = None
    daily_returns: Optional[List[float]] = None

    @property
    def length(self) -> int:
        return len(self.dates)


@dataclass
class BoundingBox:
    """Axis-aligned box in chart pixel space."""

    x0: int
    y0: int
    x1: int
    y1: int
    label: str = ""
    confidence: float = 1.0


@dataclass
class FactorAlignment:
    """Alignment between visual region and quantitative factor."""

    factor_id: str
    factor_name: str
    score: float
    bbox_label: str
    evidence: str = ""


@dataclass
class ChartImageData:
    """Rendered chart image metadata."""

    image_path: str
    chart_type: str = "candlestick_volume"
    lookback_bars: int = 60
    overlays: List[str] = field(default_factory=list)
    width: int = 1024
    height: int = 768
    dpi: int = 150
    price_min: float = 0.0
    price_max: float = 0.0
    date_start: str = ""
    date_end: str = ""
    bboxes: List[BoundingBox] = field(default_factory=list)
    factor_alignments: List[FactorAlignment] = field(default_factory=list)


@dataclass
class NewsItem:
    date: str
    headline: str
    summary: str = ""
    source: str = ""
    sentiment: Optional[float] = None
    relevance: float = 0.5


@dataclass
class FilingItem:
    date: str
    filing_type: str
    section: str = ""
    content: str = ""
    fiscal_period: str = ""


@dataclass
class AnalystReport:
    date: str
    source: str = ""
    rating: str = ""
    target_price: Optional[float] = None
    summary: str = ""


@dataclass
class TextualContext:
    news: List[NewsItem] = field(default_factory=list)
    filings: List[FilingItem] = field(default_factory=list)
    analyst_reports: List[AnalystReport] = field(default_factory=list)
    combined_summary: str = ""

    @property
    def has_text(self) -> bool:
        return bool(self.news or self.filings or self.analyst_reports or self.combined_summary)


@dataclass
class DecisionSample:
    sample_id: str = ""
    asset: str = ""
    decision_date: str = ""
    alignment_id: str = ""
    split: str = ""

    time_series: Optional[TimeSeriesData] = None
    chart_image: Optional[ChartImageData] = None
    textual_context: Optional[TextualContext] = None

    label: Optional[Dict[str, Any]] = None

    market: str = ""
    sector: str = ""
    lookback_window: int = 60
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        import dataclasses

        def _convert(obj):
            if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
                return {k: _convert(v) for k, v in dataclasses.asdict(obj).items()}
            if isinstance(obj, list):
                return [_convert(i) for i in obj]
            if isinstance(obj, dict):
                return {k: _convert(v) for k, v in obj.items()}
            if isinstance(obj, (np.integer,)):
                return int(obj)
            if isinstance(obj, (np.floating,)):
                return float(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            return obj

        return _convert(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DecisionSample":
        ts_data = d.get("time_series")
        ts = TimeSeriesData(**ts_data) if ts_data else None

        ci_data = d.get("chart_image")
        ci = None
        if ci_data:
            boxes = [BoundingBox(**b) for b in ci_data.get("bboxes", [])]
            aligns = [FactorAlignment(**a) for a in ci_data.get("factor_alignments", [])]
            payload = dict(ci_data)
            payload["bboxes"] = boxes
            payload["factor_alignments"] = aligns
            ci = ChartImageData(**payload)

        tc_data = d.get("textual_context")
        tc = None
        if tc_data:
            news = [NewsItem(**n) for n in tc_data.get("news", [])]
            filings = [FilingItem(**f) for f in tc_data.get("filings", [])]
            reports = [AnalystReport(**r) for r in tc_data.get("analyst_reports", [])]
            tc = TextualContext(
                news=news,
                filings=filings,
                analyst_reports=reports,
                combined_summary=tc_data.get("combined_summary", ""),
            )

        return cls(
            sample_id=d.get("sample_id", ""),
            asset=d.get("asset", ""),
            decision_date=d.get("decision_date", ""),
            alignment_id=d.get("alignment_id", ""),
            split=d.get("split", ""),
            time_series=ts,
            chart_image=ci,
            textual_context=tc,
            label=d.get("label"),
            market=d.get("market", ""),
            sector=d.get("sector", ""),
            lookback_window=d.get("lookback_window", 60),
            metadata=d.get("metadata", {}),
        )


@dataclass
class FinVLDataset:
    samples: List[DecisionSample] = field(default_factory=list)
    split: str = ""
    market: str = ""
    assets: List[str] = field(default_factory=list)
    date_range: tuple = ("", "")
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.samples)

    def save_jsonl(self, path: str):
        import json
        import os

        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for s in self.samples:
                f.write(json.dumps(s.to_dict(), ensure_ascii=False) + "\n")

    @classmethod
    def load_jsonl(cls, path: str) -> "FinVLDataset":
        import json

        samples = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    samples.append(DecisionSample.from_dict(json.loads(line)))
        ds = cls(samples=samples)
        if samples:
            ds.assets = list(set(s.asset for s in samples))
            ds.date_range = (samples[0].decision_date, samples[-1].decision_date)
        return ds


def validate_ohlcv_df(df: pd.DataFrame) -> pd.DataFrame:
    required = {"open", "high", "low", "close", "volume"}
    cols_lower = {c.lower(): c for c in df.columns}
    missing = required - set(cols_lower.keys())
    if missing:
        raise ValueError(f"OHLCV DataFrame missing columns: {missing}")

    rename_map = {}
    for std_name, orig_name in cols_lower.items():
        if std_name in required and orig_name != std_name:
            rename_map[orig_name] = std_name
    if rename_map:
        df = df.rename(columns=rename_map)

    if not isinstance(df.index, pd.DatetimeIndex):
        date_col = cols_lower.get("date") or cols_lower.get("datetime")
        if date_col and date_col in df.columns:
            df = df.set_index(pd.to_datetime(df[date_col]))
            df = df.drop(columns=[date_col], errors="ignore")
        else:
            df.index = pd.to_datetime(df.index)

    df = df.sort_index()
    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0)
    df = df.dropna(subset=["open", "high", "low", "close"])
    return df
