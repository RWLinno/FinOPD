"""Create auditable portfolio metrics and dependence-aware Sharpe intervals."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from finvl.evaluation.portfolio import PortfolioConfig, synchronized_portfolio
from finvl.evaluation.statistics import moving_block_bootstrap_sharpe


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--returns", nargs="+", required=True, metavar="ASSET=CSV")
    parser.add_argument("--weight", nargs="*", default=[], metavar="ASSET=WEIGHT")
    parser.add_argument("--return-column", default="net_return")
    parser.add_argument("--date-column", default="date")
    parser.add_argument("--output", required=True)
    parser.add_argument("--bootstrap-samples", type=int, default=2000)
    parser.add_argument("--block-size", type=int, default=20)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    series = {}
    for spec in args.returns:
        asset, path = spec.split("=", 1)
        df = pd.read_csv(path, parse_dates=[args.date_column]).set_index(args.date_column)
        series[asset] = df[args.return_column]
    weights = {asset: float(value) for asset, value in (x.split("=", 1) for x in args.weight)} or None
    audit, metrics = synchronized_portfolio(series, weights, PortfolioConfig())
    metrics["sharpe_bootstrap"] = moving_block_bootstrap_sharpe(
        audit["portfolio_return"].to_numpy(),
        block_size=args.block_size,
        samples=args.bootstrap_samples,
        seed=args.seed,
    )
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    audit.to_csv(output / "portfolio_daily_pnl.csv", index_label="date")
    (output / "portfolio_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
