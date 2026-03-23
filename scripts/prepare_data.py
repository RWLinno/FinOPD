"""Data preparation script for FinVL-MAS."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import defaultdict
from pathlib import Path
from typing import Callable, Dict, List

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from finvl.data.schema import FilingItem, TextualContext

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("finvl.prepare_data")


def cmd_synthetic(args):
    from finvl.data.synthetic import generate_synthetic_dataset

    dataset = generate_synthetic_dataset(
        asset=args.asset,
        n_bars=args.n_bars,
        lookback=args.lookback,
        start_date=args.start_date,
        output_dir=args.output_dir,
        seed=args.seed,
        sample_every_n=args.sample_every,
    )
    logger.info("Generated %d samples", len(dataset))


def cmd_download(args):
    from finvl.data.pipeline import fetch_ohlcv_yfinance

    for ticker in args.tickers:
        save_path = f"{args.output_dir}/{ticker}_ohlcv.csv"
        try:
            df = fetch_ohlcv_yfinance(ticker=ticker, start=args.start, end=args.end, save_path=save_path)
            logger.info("%s: %d bars saved to %s", ticker, len(df), save_path)
        except Exception as exc:
            logger.error("%s: %s", ticker, exc)


def _load_filings(path: str) -> Dict[str, List[dict]]:
    rows: Dict[str, List[dict]] = defaultdict(list)
    with Path(path).open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            asset = str(item.get("asset") or item.get("ticker") or "").strip()
            if not asset:
                continue
            item["date"] = str(item.get("date", ""))[:10]
            rows[asset].append(item)
    for asset in rows:
        rows[asset].sort(key=lambda x: x.get("date", ""))
    return rows


def _build_text_provider(rows: Dict[str, List[dict]], max_filings_per_date: int) -> Callable[[str, str], TextualContext]:
    def provider(asset: str, decision_date: str) -> TextualContext:
        picked = [r for r in rows.get(asset, []) if r.get("date", "") <= decision_date][-max_filings_per_date:]
        filings = [
            FilingItem(
                date=r.get("date", ""),
                filing_type=r.get("filing_type", "unknown"),
                section=r.get("section", ""),
                content=r.get("content", ""),
                fiscal_period=r.get("fiscal_period", ""),
            )
            for r in picked
        ]
        summary = " ".join([f"[{x.filing_type}] {x.section}: {x.content[:240].replace(chr(10), ' ')}" for x in filings])
        return TextualContext(filings=filings, combined_summary=summary)

    return provider


def cmd_build(args):
    from finvl.data.pipeline import build_dataset, load_ohlcv_csv

    ohlcv = load_ohlcv_csv(args.ohlcv_path)
    all_dates = [d.strftime("%Y-%m-%d") for d in ohlcv.index]
    if args.start:
        all_dates = [d for d in all_dates if d >= args.start]
    if args.end:
        all_dates = [d for d in all_dates if d <= args.end]

    decision_dates = all_dates[args.lookback :: args.sample_every]
    text_provider = None
    if args.filings_jsonl:
        text_provider = _build_text_provider(_load_filings(args.filings_jsonl), args.max_filings_per_date)

    dataset = build_dataset(
        ohlcv_df=ohlcv,
        asset=args.asset,
        decision_dates=decision_dates,
        chart_output_dir=f"{args.output_dir}/charts",
        lookback=args.lookback,
        market=args.market,
        text_provider=text_provider,
        split=args.split,
        enable_factor_bbox=not args.disable_factor_bbox,
    )

    out = f"{args.output_dir}/{args.asset}_dataset.jsonl"
    dataset.save_jsonl(out)
    logger.info("Saved %d samples to %s", len(dataset), out)


def main():
    parser = argparse.ArgumentParser(description="FinVL-MAS Data Preparation")
    sub = parser.add_subparsers(dest="command", required=True)

    p_syn = sub.add_parser("synthetic", help="Generate synthetic test data")
    p_syn.add_argument("--asset", default="SYNTH")
    p_syn.add_argument("--n-bars", type=int, default=500)
    p_syn.add_argument("--lookback", type=int, default=60)
    p_syn.add_argument("--start-date", default="2022-01-03")
    p_syn.add_argument("--output-dir", default="data/synthetic")
    p_syn.add_argument("--seed", type=int, default=42)
    p_syn.add_argument("--sample-every", type=int, default=5)
    p_syn.set_defaults(func=cmd_synthetic)

    p_dl = sub.add_parser("download", help="Download OHLCV from Yahoo Finance")
    p_dl.add_argument("--tickers", nargs="+", default=["AAPL", "TSLA", "MSFT"])
    p_dl.add_argument("--start", default="2020-01-01")
    p_dl.add_argument("--end", default="2024-12-31")
    p_dl.add_argument("--output-dir", default="data/raw")
    p_dl.set_defaults(func=cmd_download)

    p_build = sub.add_parser("build", help="Build tri-modal dataset from OHLCV CSV")
    p_build.add_argument("--ohlcv-path", required=True)
    p_build.add_argument("--asset", required=True)
    p_build.add_argument("--market", default="US")
    p_build.add_argument("--lookback", type=int, default=60)
    p_build.add_argument("--sample-every", type=int, default=5)
    p_build.add_argument("--start", default=None)
    p_build.add_argument("--end", default=None)
    p_build.add_argument("--output-dir", default="data/processed")
    p_build.add_argument("--split", default="train", choices=["", "train", "valid", "test"])
    p_build.add_argument("--filings-jsonl", default=None)
    p_build.add_argument("--max-filings-per-date", type=int, default=4)
    p_build.add_argument("--disable-factor-bbox", action="store_true")
    p_build.set_defaults(func=cmd_build)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
