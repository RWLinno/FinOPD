"""
ChartGeometry dataset builder.
Renders candlestick charts and extracts geometric annotations for VLM LoRA training.
Produces JSONL: {image_path, geometry_json, ticker, date}
Target: ~50K samples from 2015-2022 training window.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from finvl.data.pipeline import compute_indicators, render_chart_for_sample
from finvl.visual.geometry import GeometryExtractor

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("chart_geometry_build")


def classify_regime(df_window: pd.DataFrame) -> str:
    """Classify market regime from a price window."""
    if len(df_window) < 20:
        return "calm"
    returns = df_window["close"].pct_change().dropna()
    vol = returns.std() * np.sqrt(252)
    trend = (df_window["close"].iloc[-1] / df_window["close"].iloc[0]) - 1

    if vol > 0.35:
        return "volatile"
    elif abs(trend) > 0.15:
        return "trending"
    elif vol < 0.15:
        return "calm"
    else:
        return "ranging"


def extract_geometry(extractor: GeometryExtractor, df_window: pd.DataFrame) -> Dict[str, Any]:
    """Extract chart geometry features using rule-based extractor."""
    try:
        result = extractor.extract(df_window)
        return {
            "trend_lines": [str(t) for t in result.trendlines],
            "price_levels": [str(s) for s in result.support_resistance],
            "candle_patterns": [str(c) for c in result.candlestick_patterns],
            "chart_formations": [str(f) for f in result.formations],
            "volume_signals": [str(v) for v in result.volume_signals],
            "regime": result.regime.regime.value if hasattr(result.regime, 'regime') else classify_regime(df_window),
            "bias": result.overall_bias.value if hasattr(result.overall_bias, 'value') else "neutral",
        }
    except Exception as e:
        logger.warning(f"Geometry extraction failed: {e}")
        return {
            "trend_lines": [],
            "price_levels": [],
            "candle_patterns": [],
            "chart_formations": [],
            "volume_signals": [],
            "regime": classify_regime(df_window),
            "bias": "neutral",
        }


def build_chart_geometry_dataset(
    data_dir: str,
    output_dir: str,
    train_start: str = "2015-01-01",
    train_end: str = "2022-12-31",
    lookback: int = 60,
    sample_every: int = 5,
    max_samples: int = 60000,
) -> str:
    """Build chart geometry dataset from all available ticker CSVs."""
    raw_dir = Path(data_dir)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    charts_dir = out_dir / "charts"
    charts_dir.mkdir(parents=True, exist_ok=True)

    output_jsonl = out_dir / "train.jsonl"
    extractor = GeometryExtractor()

    csv_files = list(raw_dir.glob("*_ohlcv.csv"))
    if not csv_files:
        logger.error(f"No CSV files found in {raw_dir}")
        return str(output_jsonl)

    total_samples = 0
    with open(output_jsonl, "w", encoding="utf-8") as fout:
        for csv_path in sorted(csv_files):
            ticker = csv_path.stem.replace("_ohlcv", "")
            logger.info(f"Processing {ticker}...")

            try:
                df = pd.read_csv(csv_path, parse_dates=True, index_col=0)
                df.columns = [c.lower() for c in df.columns]
                df = compute_indicators(df)
            except Exception as e:
                logger.warning(f"Failed to load {csv_path}: {e}")
                continue

            mask = (df.index >= pd.Timestamp(train_start)) & (df.index <= pd.Timestamp(train_end))
            df_train = df[mask]

            if len(df_train) < lookback + 10:
                logger.warning(f"{ticker}: insufficient data ({len(df_train)} bars)")
                continue

            dates = df_train.index[lookback::sample_every]
            ticker_samples = 0

            for dt in dates:
                if total_samples >= max_samples:
                    break

                window = df_train.loc[df_train.index <= dt].iloc[-lookback:]
                if len(window) < lookback:
                    continue

                date_str = dt.strftime("%Y-%m-%d")
                geometry = extract_geometry(extractor, window)

                chart_data = render_chart_for_sample(
                    window, ticker, date_str,
                    str(charts_dir),
                    enable_factor_bbox=False,
                )

                sample = {
                    "image_path": str(charts_dir / chart_data.image_path),
                    "geometry_json": geometry,
                    "ticker": ticker,
                    "date": date_str,
                }
                fout.write(json.dumps(sample, ensure_ascii=False) + "\n")
                total_samples += 1
                ticker_samples += 1

            logger.info(f"  {ticker}: {ticker_samples} samples")

            if total_samples >= max_samples:
                logger.info(f"Reached max_samples={max_samples}, stopping.")
                break

    logger.info(f"Total: {total_samples} samples written to {output_jsonl}")
    return str(output_jsonl)


def main():
    parser = argparse.ArgumentParser(description="Build ChartGeometry dataset for VLM LoRA training")
    parser.add_argument("--data-dir", default="data/raw", help="Directory with *_ohlcv.csv files")
    parser.add_argument("--output-dir", default="data/chart_geometry", help="Output directory")
    parser.add_argument("--train-start", default="2015-01-01")
    parser.add_argument("--train-end", default="2022-12-31")
    parser.add_argument("--lookback", type=int, default=60)
    parser.add_argument("--sample-every", type=int, default=5)
    parser.add_argument("--max-samples", type=int, default=60000)
    args = parser.parse_args()

    build_chart_geometry_dataset(
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        train_start=args.train_start,
        train_end=args.train_end,
        lookback=args.lookback,
        sample_every=args.sample_every,
        max_samples=args.max_samples,
    )


if __name__ == "__main__":
    main()
