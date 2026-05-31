"""
Live-Forward Daemon: daily inference on latest market data.
Pulls yfinance data each day and runs full FinOPD pipeline.
Results written to outputs/live_forward/YYYY-MM-DD.json.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from finvl.core.config import load_config
from finvl.core.types import DecisionOutput
from finvl.data.pipeline import fetch_ohlcv_yfinance, compute_indicators
from finvl.workflow.orchestrator import AgentOrchestrator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("live_forward")


class LiveForwardDaemon:
    """
    Runs daily inference on latest market data.
    Accumulates evidence for live-forward evaluation track.
    """

    def __init__(self, config: Dict[str, Any], output_dir: str = "outputs/live_forward"):
        self.config = config
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.orchestrator = AgentOrchestrator(config)

    def run_single_day(self, ticker: str, date: str = None) -> Dict[str, Any]:
        """Run inference for a single ticker on a given date."""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        end_date = date
        start_date = (datetime.strptime(date, "%Y-%m-%d") - timedelta(days=120)).strftime("%Y-%m-%d")

        try:
            df = fetch_ohlcv_yfinance(ticker, start_date, end_date)
            df = compute_indicators(df)
        except Exception as e:
            logger.error(f"Failed to fetch data for {ticker}: {e}")
            return {"ticker": ticker, "date": date, "error": str(e)}

        if len(df) < 30:
            return {"ticker": ticker, "date": date, "error": "Insufficient data"}

        window = df.tail(60)
        inputs = {
            "ohlcv_df": window,
            "current_price": float(window["close"].iloc[-1]),
            "asset": ticker,
            "timeframe": "daily",
            "events": [],
        }

        try:
            decision = asyncio.run(self.orchestrator.run(inputs))
            result = {
                "ticker": ticker,
                "date": date,
                "action": decision.action.value if hasattr(decision.action, "value") else str(decision.action),
                "confidence": decision.confidence,
                "position_size_pct": decision.position_size_pct,
                "rationale": decision.rationale[:500],
                "current_price": float(window["close"].iloc[-1]),
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            result = {"ticker": ticker, "date": date, "error": str(e)}

        return result

    def run_daily(self, tickers: List[str], date: str = None):
        """Run inference for all tickers and save results."""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        results = []
        for ticker in tickers:
            logger.info(f"Processing {ticker}...")
            result = self.run_single_day(ticker, date)
            results.append(result)

        output_file = self.output_dir / f"{date}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        logger.info(f"Live-forward results saved: {output_file}")
        return results

    def run_daemon(self, tickers: List[str], interval_hours: int = 24):
        """Run as a daemon, executing daily."""
        logger.info(f"Starting live-forward daemon (interval: {interval_hours}h)")
        while True:
            try:
                self.run_daily(tickers)
            except Exception as e:
                logger.error(f"Daemon iteration failed: {e}")
            time.sleep(interval_hours * 3600)


def main():
    parser = argparse.ArgumentParser(description="Live-Forward Daemon")
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--tickers", nargs="+",
                       default=["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN"])
    parser.add_argument("--output", default="outputs/live_forward/")
    parser.add_argument("--date", default=None)
    parser.add_argument("--daemon", action="store_true")
    args = parser.parse_args()

    cfg = load_config(args.config)
    daemon = LiveForwardDaemon(cfg, args.output)

    if args.daemon:
        daemon.run_daemon(args.tickers)
    else:
        daemon.run_daily(args.tickers, args.date)


if __name__ == "__main__":
    main()
