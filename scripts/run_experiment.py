"""
Main experiment runner for FinVL-MAS.
Loads config, runs the multi-agent pipeline over a date range,
backtests, and reports metrics.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from finvl.core.config import load_config
from finvl.core.memory import TraceMemory
from finvl.core.scenario import FinVLScenario, TemporalSplit
from finvl.core.types import DecisionOutput
from finvl.data.provider import OHLCVProvider
from finvl.evaluation.analysis import RegimeAnalyzer, format_metrics_table
from finvl.evaluation.backtest import BacktestConfig, BacktestResult, VectorizedBacktester
from finvl.workflow.orchestrator import AgentOrchestrator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("finvl.experiment")


async def run_pipeline_on_dates(
    orchestrator: AgentOrchestrator,
    provider: OHLCVProvider,
    dates: List[str],
    lookback: int = 60,
) -> List[Dict[str, Any]]:
    """Run the multi-agent pipeline on each date."""
    decisions = []
    for i, date in enumerate(dates):
        try:
            window_df = provider.get_window(date, lookback=lookback)
            if len(window_df) < 10:
                continue

            inputs = {
                "ohlcv_df": window_df,
                "current_price": float(window_df["close"].iloc[-1]),
                "asset": "ASSET",
                "timeframe": "daily",
                "start_date": window_df.index[0].strftime("%Y-%m-%d"),
                "end_date": date,
            }

            decision = await orchestrator.run(inputs)
            decisions.append({"date": date, "decision": decision})

            if (i + 1) % 50 == 0:
                logger.info(f"Processed {i + 1}/{len(dates)} dates")

        except Exception as e:
            logger.warning(f"Failed on {date}: {e}")
            decisions.append({
                "date": date,
                "decision": DecisionOutput(rationale=f"Error: {e}"),
            })

    return decisions


def main():
    parser = argparse.ArgumentParser(description="FinVL-MAS Experiment Runner")
    parser.add_argument("--config", default="configs/default.yaml", help="Config file path")
    parser.add_argument("--data", default=None, help="Override data path")
    parser.add_argument("--output-dir", default="outputs/experiments", help="Output directory")
    parser.add_argument("--max-dates", type=int, default=None, help="Limit number of dates")
    args = parser.parse_args()

    cfg = load_config(args.config)

    # Setup output
    exp_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir) / exp_id
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save config snapshot
    with open(output_dir / "config.json", "w") as f:
        json.dump(cfg, f, indent=2)

    # Load data
    data_path = args.data or os.path.join(
        cfg.get("data", {}).get("data_dir", "data/processed"),
        cfg.get("data", {}).get("ohlcv_file", "data.csv"),
    )

    if not Path(data_path).exists():
        logger.error(f"Data file not found: {data_path}. Please provide OHLCV data.")
        logger.info("Example: python scripts/run_experiment.py --data data/processed/csi300.csv")
        sys.exit(1)

    provider = OHLCVProvider(data_path)

    # Setup scenario
    eval_cfg = cfg.get("evaluation", {})
    split_cfg = eval_cfg.get("temporal_split", {})
    test_start = split_cfg.get("test_start", "2017-01-01")
    test_end = split_cfg.get("test_end", "2020-12-31")

    test_dates = provider.trading_dates(test_start, test_end)
    if args.max_dates:
        test_dates = test_dates[: args.max_dates]

    logger.info(f"Running on {len(test_dates)} test dates ({test_start} to {test_end})")

    # Setup orchestrator
    orchestrator = AgentOrchestrator(cfg)

    # Run pipeline
    decisions = asyncio.run(run_pipeline_on_dates(
        orchestrator, provider, test_dates,
        lookback=cfg.get("scenario", {}).get("lookback_window", 60),
    ))

    # Backtest
    bt_config = BacktestConfig(
        transaction_cost_bps=eval_cfg.get("transaction_cost_bps", 15),
        slippage_bps=eval_cfg.get("slippage_bps", 5),
        execution_delay_days=eval_cfg.get("execution_delay_days", 1),
    )
    backtester = VectorizedBacktester(bt_config)
    test_df = provider.get_date_range(test_start, test_end)
    result = backtester.run(decisions, test_df)

    # Report
    print("\n" + "=" * 60)
    print("EXPERIMENT RESULTS")
    print("=" * 60)
    for k, v in sorted(result.metrics.items()):
        if isinstance(v, float):
            print(f"  {k:30s}: {v:>10.4f}")
        else:
            print(f"  {k:30s}: {v}")

    # Save results
    with open(output_dir / "metrics.json", "w") as f:
        json.dump(result.metrics, f, indent=2)

    # Save decisions
    dec_records = []
    for d in decisions:
        dec: DecisionOutput = d["decision"]
        dec_records.append({
            "date": d["date"],
            "action": dec.action.value,
            "conviction": dec.conviction.value,
            "confidence": dec.confidence,
            "position_pct": dec.position_size_pct,
            "rationale": dec.rationale[:200],
        })
    pd.DataFrame(dec_records).to_csv(output_dir / "decisions.csv", index=False)

    logger.info(f"Results saved to {output_dir}")
    print(f"\nResults saved to: {output_dir}")


if __name__ == "__main__":
    main()
