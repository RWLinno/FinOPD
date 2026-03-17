"""
Data preparation script for FinVL-MAS.

Supports:
  1. Download real OHLCV data from Yahoo Finance
  2. Generate synthetic test data
  3. Build tri-modal aligned dataset (JSONL + chart images)
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("finvl.prepare_data")


def cmd_synthetic(args):
    """Generate synthetic test dataset."""
    from finvl.data.synthetic import generate_synthetic_dataset

    logger.info("Generating synthetic dataset...")
    dataset = generate_synthetic_dataset(
        asset=args.asset,
        n_bars=args.n_bars,
        lookback=args.lookback,
        start_date=args.start_date,
        output_dir=args.output_dir,
        seed=args.seed,
        sample_every_n=args.sample_every,
    )
    logger.info(f"Generated {len(dataset)} samples")
    logger.info(f"Output: {args.output_dir}/")

    # Print sample structure
    if dataset.samples:
        s = dataset.samples[0]
        logger.info(f"Sample structure:")
        logger.info(f"  sample_id: {s.sample_id}")
        logger.info(f"  decision_date: {s.decision_date}")
        logger.info(f"  time_series: {s.time_series.length} bars" if s.time_series else "  time_series: None")
        logger.info(f"  chart_image: {s.chart_image.image_path}" if s.chart_image else "  chart_image: None")
        logger.info(f"  textual_context: {s.textual_context.has_text}" if s.textual_context else "  textual_context: None")
        logger.info(f"  label: {s.label}")


def cmd_download(args):
    """Download real OHLCV data from Yahoo Finance."""
    from finvl.data.pipeline import fetch_ohlcv_yfinance

    for ticker in args.tickers:
        save_path = f"{args.output_dir}/{ticker}_ohlcv.csv"
        try:
            df = fetch_ohlcv_yfinance(
                ticker=ticker,
                start=args.start,
                end=args.end,
                save_path=save_path,
            )
            logger.info(f"{ticker}: {len(df)} bars saved to {save_path}")
        except Exception as e:
            logger.error(f"{ticker}: {e}")


def cmd_build(args):
    """Build tri-modal aligned dataset from existing OHLCV data."""
    from finvl.data.pipeline import build_dataset, load_ohlcv_csv
    from finvl.data.schema import FinVLDataset

    ohlcv = load_ohlcv_csv(args.ohlcv_path)
    all_dates = [d.strftime("%Y-%m-%d") for d in ohlcv.index]

    # Filter to specified range
    if args.start:
        all_dates = [d for d in all_dates if d >= args.start]
    if args.end:
        all_dates = [d for d in all_dates if d <= args.end]

    decision_dates = all_dates[args.lookback::args.sample_every]
    logger.info(f"Building dataset: {len(decision_dates)} decision dates")

    dataset = build_dataset(
        ohlcv_df=ohlcv,
        asset=args.asset,
        decision_dates=decision_dates,
        chart_output_dir=f"{args.output_dir}/charts",
        lookback=args.lookback,
        market=args.market,
    )

    jsonl_path = f"{args.output_dir}/{args.asset}_dataset.jsonl"
    dataset.save_jsonl(jsonl_path)
    logger.info(f"Saved {len(dataset)} samples to {jsonl_path}")


def main():
    parser = argparse.ArgumentParser(description="FinVL-MAS Data Preparation")
    sub = parser.add_subparsers(dest="command", required=True)

    # Synthetic
    p_syn = sub.add_parser("synthetic", help="Generate synthetic test data")
    p_syn.add_argument("--asset", default="SYNTH", help="Asset name")
    p_syn.add_argument("--n-bars", type=int, default=500)
    p_syn.add_argument("--lookback", type=int, default=60)
    p_syn.add_argument("--start-date", default="2022-01-03")
    p_syn.add_argument("--output-dir", default="data/synthetic")
    p_syn.add_argument("--seed", type=int, default=42)
    p_syn.add_argument("--sample-every", type=int, default=5)
    p_syn.set_defaults(func=cmd_synthetic)

    # Download
    p_dl = sub.add_parser("download", help="Download OHLCV from Yahoo Finance")
    p_dl.add_argument("--tickers", nargs="+", default=["AAPL", "TSLA", "MSFT"])
    p_dl.add_argument("--start", default="2020-01-01")
    p_dl.add_argument("--end", default="2024-12-31")
    p_dl.add_argument("--output-dir", default="data/raw")
    p_dl.set_defaults(func=cmd_download)

    # Build
    p_build = sub.add_parser("build", help="Build tri-modal dataset from OHLCV CSV")
    p_build.add_argument("--ohlcv-path", required=True)
    p_build.add_argument("--asset", required=True)
    p_build.add_argument("--market", default="US")
    p_build.add_argument("--lookback", type=int, default=60)
    p_build.add_argument("--sample-every", type=int, default=5)
    p_build.add_argument("--start", default=None)
    p_build.add_argument("--end", default=None)
    p_build.add_argument("--output-dir", default="data/processed")
    p_build.set_defaults(func=cmd_build)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
