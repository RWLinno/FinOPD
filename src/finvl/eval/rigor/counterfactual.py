"""
Counterfactual Perturbation Analysis.
Three perturbation types to distinguish reasoning from memorization:
1. News sentiment inversion
2. Financial figure randomization
3. Date token replacement
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from finvl.core.config import load_config
from finvl.data.provider import OHLCVProvider
from finvl.evaluation.backtest import BacktestConfig, VectorizedBacktester
from finvl.evaluation.metrics import sharpe_ratio
from finvl.workflow.orchestrator import AgentOrchestrator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("counterfactual")


class CounterfactualPerturbation:
    """Applies counterfactual perturbations to test inputs."""

    @staticmethod
    def flip_news_sentiment(events: List[Dict]) -> List[Dict]:
        """Invert all sentiment polarity in textual inputs."""
        flipped = []
        for event in events:
            e = event.copy()
            sentiment = e.get("sentiment", "neutral")
            if sentiment == "positive":
                e["sentiment"] = "negative"
            elif sentiment == "negative":
                e["sentiment"] = "positive"
            content = e.get("content", "")
            for pos, neg in [("bullish", "bearish"), ("growth", "decline"),
                           ("profit", "loss"), ("surge", "plunge")]:
                content = content.replace(pos, f"__{neg}__")
                content = content.replace(neg, pos)
                content = content.replace(f"__{neg}__", neg)
            e["content"] = content
            flipped.append(e)
        return flipped

    @staticmethod
    def randomize_figures(events: List[Dict]) -> List[Dict]:
        """Replace reported numbers with random values."""
        import re
        randomized = []
        for event in events:
            e = event.copy()
            content = e.get("content", "")
            numbers = re.findall(r'\d+\.?\d*', content)
            for num in numbers:
                try:
                    val = float(num)
                    new_val = val * np.random.uniform(0.5, 2.0)
                    content = content.replace(num, f"{new_val:.2f}", 1)
                except ValueError:
                    pass
            e["content"] = content
            randomized.append(e)
        return randomized

    @staticmethod
    def replace_dates(events: List[Dict]) -> List[Dict]:
        """Substitute actual dates with shuffled alternatives."""
        import re
        replaced = []
        for event in events:
            e = event.copy()
            content = e.get("content", "")
            dates = re.findall(r'\d{4}-\d{2}-\d{2}', content)
            for date in dates:
                fake_year = np.random.choice([2018, 2019, 2020, 2021])
                fake_date = f"{fake_year}-{np.random.randint(1,13):02d}-{np.random.randint(1,29):02d}"
                content = content.replace(date, fake_date, 1)
            e["content"] = content
            replaced.append(e)
        return replaced


def run_counterfactual_experiment(
    config: Dict[str, Any],
    provider: OHLCVProvider,
    dates: List[str],
    perturbation_type: str,
) -> float:
    """Run experiment with a specific perturbation and return Sharpe."""
    orchestrator = AgentOrchestrator(config)
    perturbation = CounterfactualPerturbation()

    decisions = []
    for date in dates:
        try:
            window_df = provider.get_window(date, lookback=60)
            if len(window_df) < 10:
                continue

            events = [{"content": f"Market data for {date}", "sentiment": "neutral"}]

            if perturbation_type == "news_flip":
                events = perturbation.flip_news_sentiment(events)
            elif perturbation_type == "figure_rand":
                events = perturbation.randomize_figures(events)
            elif perturbation_type == "date_replace":
                events = perturbation.replace_dates(events)

            inputs = {
                "ohlcv_df": window_df,
                "current_price": float(window_df["close"].iloc[-1]),
                "asset": "ASSET",
                "timeframe": "daily",
                "events": events,
            }
            decision = asyncio.run(orchestrator.run(inputs))
            decisions.append({"date": date, "decision": decision})
        except Exception:
            from finvl.core.types import DecisionOutput
            decisions.append({"date": date, "decision": DecisionOutput()})

    bt = VectorizedBacktester(BacktestConfig())
    test_df = provider.get_date_range(dates[0], dates[-1])
    result = bt.run(decisions, test_df)
    return result.metrics.get("sharpe_ratio", 0.0)


def main():
    parser = argparse.ArgumentParser(description="Counterfactual Perturbation Analysis")
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--checkpoint", default="outputs/opsd_full/")
    parser.add_argument("--data", default="data/processed/us_dow30.csv")
    parser.add_argument("--output", default="outputs/counterfactual/")
    parser.add_argument("--max-dates", type=int, default=100)
    parser.add_argument("--seeds", nargs="+", type=int, default=[42, 123, 456])
    args = parser.parse_args()

    cfg = load_config(args.config)
    provider = OHLCVProvider(args.data)

    split = cfg.get("evaluation", {}).get("temporal_split", {})
    dates = provider.trading_dates(
        split.get("test_start", "2025-01-01"),
        split.get("test_end", "2025-12-31"),
    )[:args.max_dates]

    perturbation_types = ["none", "news_flip", "figure_rand", "date_replace"]
    results = {}

    for ptype in perturbation_types:
        logger.info(f"Running perturbation: {ptype}")
        sharpes = []
        for seed in args.seeds:
            np.random.seed(seed)
            sr = run_counterfactual_experiment(cfg, provider, dates, ptype)
            sharpes.append(sr)
        results[ptype] = {
            "mean_sharpe": float(np.mean(sharpes)),
            "std_sharpe": float(np.std(sharpes)),
        }
        logger.info(f"  {ptype}: SR={np.mean(sharpes):.4f} ± {np.std(sharpes):.4f}")

    baseline_sr = results["none"]["mean_sharpe"]
    for ptype in ["news_flip", "figure_rand", "date_replace"]:
        delta = results[ptype]["mean_sharpe"] - baseline_sr
        results[ptype]["delta_sr"] = delta
        logger.info(f"  Delta SR ({ptype}): {delta:.4f}")

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_dir / "counterfactual_results.json", "w") as f:
        json.dump(results, f, indent=2)

    logger.info(f"Results saved to {output_dir}")


if __name__ == "__main__":
    main()
