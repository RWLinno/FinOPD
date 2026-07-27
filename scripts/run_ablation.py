"""
Ablation suite runner for FinVL-MAS.
Runs the full system and all ablation variants, then generates a comparison table.
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

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from finvl.core.config import load_config, merge_ablation_config
from finvl.core.types import DecisionOutput
from finvl.data.provider import OHLCVProvider
from finvl.evaluation.analysis import format_metrics_table
from finvl.evaluation.backtest import BacktestConfig, VectorizedBacktester
from finvl.workflow.orchestrator import AgentOrchestrator
from finvl.visual.vlm_client import VLMClient, VLMRouter

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("finvl.ablation")


ABLATION_CONFIGS = {
    "A1_full": None,  # Use default config as-is
    "A2_no_visual": "configs/ablations/no_visual.yaml",
    "A3_raw_chart": "configs/ablations/raw_chart.yaml",
    "A4_single_agent": "configs/ablations/single_agent.yaml",
    "A5_no_gating": "configs/ablations/no_gating.yaml",
    "A6_no_event": "configs/ablations/no_event.yaml",
    "A7_no_risk": "configs/ablations/no_risk.yaml",
    "A8_rule_only": "configs/ablations/rule_only.yaml",
}


async def run_variant(
    config: Dict[str, Any],
    provider: OHLCVProvider,
    dates: List[str],
    lookback: int,
    asset: str,
) -> Dict[str, float]:
    """Run a single ablation variant and return metrics."""
    orchestrator = AgentOrchestrator(config)

    decisions = []
    for date in dates:
        try:
            window_df = provider.get_window(date, lookback=lookback, asset=asset)
            if len(window_df) < 10:
                continue
            chart_path = None
            try:
                from finvl.visual.renderer import ChartRenderer

                chart_dir = config.get("chart", {}).get("output_dir", "outputs/ablation_charts")
                renderer = ChartRenderer({**config.get("chart", {}), "output_dir": chart_dir})
                chart_path, _ = renderer.render_candlestick(window_df, asset=asset, save_path=f"{chart_dir}/{asset}_{date}.png")
            except Exception:
                chart_path = None

            vlm_cfg = config.get("vlm", {})
            has_key = bool(vlm_cfg.get("api_key") or os.getenv("OPENAI_API_KEY"))
            vlm_runtime = None
            if chart_path and has_key:
                vlm_runtime = VLMRouter(vlm_cfg) if vlm_cfg.get("routes") else VLMClient(vlm_cfg)
            inputs = {
                "ohlcv_df": window_df,
                "current_price": float(window_df["close"].iloc[-1]),
                "asset": asset,
                "timeframe": "daily",
                "start_date": window_df.index[0].strftime("%Y-%m-%d"),
                "end_date": date,
                "events": [],
            }
            if chart_path:
                inputs["chart_image_path"] = chart_path
            if chart_path and vlm_runtime is not None:
                inputs["vlm_client"] = vlm_runtime
            decision = await orchestrator.run(inputs)
            decisions.append({"date": date, "decision": decision})
        except Exception:
            decisions.append({
                "date": date,
                "decision": DecisionOutput(),
            })

    bt = VectorizedBacktester(BacktestConfig(
        transaction_cost_bps=config.get("evaluation", {}).get("transaction_cost_bps", 15),
    ))
    test_df = provider.get_date_range(dates[0], dates[-1], asset=asset)
    result = bt.run(decisions, test_df)
    return result.metrics


def main():
    parser = argparse.ArgumentParser(description="FinVL-MAS Ablation Suite")
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--data", required=True, help="OHLCV data path")
    parser.add_argument("--max-dates", type=int, default=50)
    parser.add_argument("--output-dir", default="outputs/experiments")
    parser.add_argument("--asset", required=True)
    args = parser.parse_args()

    base_cfg = load_config(args.config)
    provider = OHLCVProvider(args.data)

    eval_cfg = base_cfg.get("evaluation", {})
    split = eval_cfg.get("temporal_split", {})
    test_dates = provider.trading_dates(
        split.get("test_start", "2017-01-01"),
        split.get("test_end", "2020-12-31"), asset=args.asset,
    )
    if not test_dates:
        # Fallback for custom datasets whose date range does not overlap default config.
        all_dates = provider.trading_dates(*provider.date_range, asset=args.asset)
        test_dates = all_dates
    if args.max_dates:
        test_dates = test_dates[: args.max_dates]

    lookback = base_cfg.get("scenario", {}).get("lookback_window", 60)
    all_results: Dict[str, Dict[str, float]] = {}

    for name, ablation_path in ABLATION_CONFIGS.items():
        logger.info(f"Running ablation: {name}")
        if ablation_path:
            cfg = merge_ablation_config(args.config, ablation_path)
        else:
            cfg = base_cfg

        metrics = asyncio.run(
            run_variant(cfg, provider, test_dates, lookback, args.asset)
        )
        all_results[name] = metrics
        logger.info(f"  {name}: Sharpe={metrics.get('sharpe_ratio', 0):.3f}")

    # Print comparison table
    print("\n" + "=" * 60)
    print("ABLATION RESULTS")
    print("=" * 60)
    table = format_metrics_table(all_results)
    print(table)

    # Save results
    exp_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir) / f"ablation_{exp_id}"
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(output_dir / "ablation_results.json", "w") as f:
        json.dump(all_results, f, indent=2)
    with open(output_dir / "ablation_table.md", "w") as f:
        f.write(table)

    print(f"\nResults saved to: {output_dir}")


if __name__ == "__main__":
    main()
