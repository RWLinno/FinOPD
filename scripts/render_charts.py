"""
Chart rendering utility. Renders candlestick charts for a date range.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pandas as pd

from finvl.data.provider import OHLCVProvider
from finvl.visual.renderer import ChartRenderer


def main():
    parser = argparse.ArgumentParser(description="Render financial charts")
    parser.add_argument("--data", required=True, help="OHLCV CSV path")
    parser.add_argument("--output-dir", default="data/charts")
    parser.add_argument("--start", default=None, help="Start date")
    parser.add_argument("--end", default=None, help="End date")
    parser.add_argument("--lookback", type=int, default=60)
    parser.add_argument("--asset", default="ASSET")
    args = parser.parse_args()

    provider = OHLCVProvider(args.data)
    renderer = ChartRenderer({"output_dir": args.output_dir})

    end_date = args.end or provider.date_range[1]
    window_df = provider.get_window(end_date, lookback=args.lookback)

    overlays = [
        {"type": "sma", "periods": [5, 20]},
        {"type": "bollinger", "period": 20, "std": 2},
    ]
    path, meta = renderer.render_candlestick(window_df, asset=args.asset, overlays=overlays)
    print(f"Chart saved to: {path}")
    print(f"  Period: {meta.start_date} to {meta.end_date}")
    print(f"  Price range: {meta.price_min:.2f} - {meta.price_max:.2f}")


if __name__ == "__main__":
    main()
