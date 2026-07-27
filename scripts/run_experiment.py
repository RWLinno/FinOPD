"""Main experiment runner for FinVL-MAS."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from finvl.core.config import load_config
from finvl.core.types import DecisionOutput
from finvl.data.provider import OHLCVProvider
from finvl.evaluation.backtest import BacktestConfig, VectorizedBacktester
from finvl.visual.vlm_client import VLMClient, VLMRouter
from finvl.workflow.orchestrator import AgentOrchestrator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("finvl.experiment")


def _build_vlm_runtime(cfg: Dict[str, Any]):
    agent_cfg = cfg.get("agents", {}).get("chart_analyst", {})
    if not agent_cfg.get("use_vlm", False):
        return None

    vlm_cfg = cfg.get("vlm", {})
    api_key = vlm_cfg.get("api_key") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.warning("VLM is enabled but OPENAI_API_KEY is missing; fallback to rule-only chart analysis")
        return None

    if vlm_cfg.get("routes"):
        return VLMRouter(vlm_cfg)
    return VLMClient(vlm_cfg)


def _build_chart_renderer(cfg: Dict[str, Any], chart_dir: str):
    try:
        from finvl.visual.renderer import ChartRenderer
    except Exception as exc:
        logger.warning("Chart renderer unavailable, fallback to no-image mode: %s", exc)
        return None

    chart_cfg = dict(cfg.get("chart", {}))
    chart_cfg["output_dir"] = chart_dir
    return ChartRenderer(chart_cfg)


async def run_pipeline_on_dates(
    orchestrator: AgentOrchestrator,
    provider: OHLCVProvider,
    dates: List[str],
    lookback: int,
    renderer: Optional[object],
    vlm_runtime: Optional[object],
    asset: str,
) -> List[Dict[str, Any]]:
    decisions = []
    for i, date in enumerate(dates):
        try:
            window_df = provider.get_window(date, lookback=lookback, asset=asset)
            if len(window_df) < 10:
                continue

            chart_path = None
            if renderer is not None:
                try:
                    chart_path, _ = renderer.render_candlestick(
                        window_df,
                        asset=asset,
                        overlays=[{"type": "sma", "periods": [5, 20]}, {"type": "bollinger", "period": 20, "std": 2}],
                        save_path=os.path.join(renderer.output_dir, f"{asset}_{date}.png"),
                    )
                except Exception as exc:
                    logger.warning("Chart rendering failed on %s: %s", date, exc)
                    chart_path = None

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

            if (i + 1) % 50 == 0:
                logger.info("Processed %d/%d dates", i + 1, len(dates))

        except Exception as exc:
            logger.warning("Failed on %s: %s", date, exc)
            decisions.append({"date": date, "decision": DecisionOutput(rationale=f"Error: {exc}")})

    return decisions


def main():
    parser = argparse.ArgumentParser(description="FinVL-MAS Experiment Runner")
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--data", default=None)
    parser.add_argument("--output-dir", default="outputs/experiments")
    parser.add_argument("--max-dates", type=int, default=None)
    parser.add_argument("--ablation-suite", action="store_true")
    args = parser.parse_args()

    cfg = load_config(args.config)

    exp_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir) / exp_id
    output_dir.mkdir(parents=True, exist_ok=True)
    chart_dir = output_dir / "charts"
    chart_dir.mkdir(parents=True, exist_ok=True)

    with open(output_dir / "config.json", "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

    repro = {
        "timestamp": exp_id,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "config_path": args.config,
        "data_path": str(args.data or "default"),
    }
    try:
        repro["git_commit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(Path(__file__).parent.parent), stderr=subprocess.DEVNULL).decode().strip()
        repro["git_branch"] = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=str(Path(__file__).parent.parent), stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        pass
    with open(output_dir / "reproducibility.json", "w", encoding="utf-8") as f:
        json.dump(repro, f, indent=2)

    data_path = args.data or os.path.join(cfg.get("data", {}).get("data_dir", "data/processed"), cfg.get("data", {}).get("ohlcv_file", "data.csv"))
    if not Path(data_path).exists():
        logger.error("Data file not found: %s", data_path)
        sys.exit(1)

    provider = OHLCVProvider(data_path)
    asset = cfg.get("scenario", {}).get("market", "ASSET").upper()
    split_cfg = cfg.get("evaluation", {}).get("temporal_split", {})
    test_start = split_cfg.get("test_start", "2017-01-01")
    test_end = split_cfg.get("test_end", "2020-12-31")
    test_dates = provider.trading_dates(test_start, test_end, asset=asset)
    if not test_dates:
        logger.warning("Configured test range has no data, fallback to provider full range")
        test_dates = provider.trading_dates(*provider.date_range, asset=asset)
    if args.max_dates:
        test_dates = test_dates[: args.max_dates]

    orchestrator = AgentOrchestrator(cfg)
    renderer = _build_chart_renderer(cfg, str(chart_dir))
    vlm_runtime = _build_vlm_runtime(cfg)

    decisions = asyncio.run(
        run_pipeline_on_dates(
            orchestrator=orchestrator,
            provider=provider,
            dates=test_dates,
            lookback=cfg.get("scenario", {}).get("lookback_window", 60),
            renderer=renderer,
            vlm_runtime=vlm_runtime,
            asset=asset,
        )
    )

    eval_cfg = cfg.get("evaluation", {})
    backtester = VectorizedBacktester(
        BacktestConfig(
            transaction_cost_bps=eval_cfg.get("transaction_cost_bps", 15),
            slippage_bps=eval_cfg.get("slippage_bps", 5),
            execution_delay_days=eval_cfg.get("execution_delay_days", 1),
        )
    )

    test_df = provider.get_date_range(test_start, test_end)
    result = backtester.run(decisions, test_df)

    with open(output_dir / "metrics.json", "w", encoding="utf-8") as f:
        json.dump(result.metrics, f, indent=2)

    rows = []
    for d in decisions:
        dec: DecisionOutput = d["decision"]
        rows.append({
            "date": d["date"],
            "action": dec.action.value,
            "conviction": dec.conviction.value,
            "confidence": dec.confidence,
            "position_pct": dec.position_size_pct,
            "rationale": dec.rationale[:240],
        })
    pd.DataFrame(rows).to_csv(output_dir / "decisions.csv", index=False)

    print("\nEXPERIMENT RESULTS")
    for k, v in sorted(result.metrics.items()):
        if isinstance(v, float):
            print(f"{k:30s}: {v:>10.4f}")
        else:
            print(f"{k:30s}: {v}")
    print(f"\nResults saved to: {output_dir}")

    if args.ablation_suite:
        cmd = [
            sys.executable,
            str(Path(__file__).parent / "run_ablation.py"),
            "--config",
            args.config,
            "--data",
            data_path,
            "--max-dates",
            str(args.max_dates or 50),
            "--output-dir",
            str(Path(args.output_dir)),
        ]
        import subprocess as sp

        sp.run(cmd)


if __name__ == "__main__":
    main()
