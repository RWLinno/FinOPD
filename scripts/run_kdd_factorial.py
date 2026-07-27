"""Audit and aggregate the locked KDD mechanism matrix.

This script never substitutes a proxy for a missing arm. Each arm/seed must
provide a run manifest and one cost-adjusted daily-return file per asset before
portfolio metrics or statistical comparisons are emitted.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from finvl.evaluation.portfolio import PortfolioConfig, synchronized_portfolio
from finvl.evaluation.statistics import holm_adjust, moving_block_bootstrap_sharpe


def _load_run(
    run_dir: Path,
    arm: str,
    seed: int,
    assets: list[str],
    protocol: dict[str, Any],
) -> tuple[dict[str, pd.Series] | None, list[str]]:
    missing: list[str] = []
    manifest_path = run_dir / "run_manifest.json"
    if not manifest_path.is_file():
        return None, [str(manifest_path)]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = {"arm": arm, "seed": seed, "split": protocol["split"]}
    for key, value in expected.items():
        if manifest.get(key) != value:
            missing.append(f"{manifest_path}:{key}={value!r}")
    checkpoint = manifest.get("checkpoint")
    checkpoint_path = Path(checkpoint) if checkpoint else None
    if checkpoint_path is not None and not checkpoint_path.is_absolute():
        checkpoint_path = run_dir / checkpoint_path
    if checkpoint_path is None or not checkpoint_path.exists():
        missing.append(f"{manifest_path}:checkpoint")

    returns: dict[str, pd.Series] = {}
    start = pd.Timestamp(protocol["test_start"])
    end = pd.Timestamp(protocol["test_end"])
    for asset in assets:
        path = run_dir / asset / "daily_returns.csv"
        if not path.is_file():
            missing.append(str(path))
            continue
        frame = pd.read_csv(path, parse_dates=["date"])
        if "net_return" not in frame:
            missing.append(f"{path}:net_return")
            continue
        frame = frame.loc[
            (frame["date"] >= start) & (frame["date"] <= end),
            ["date", "net_return"],
        ]
        net_return = pd.to_numeric(frame["net_return"], errors="coerce")
        if (
            frame.empty
            or frame["date"].duplicated().any()
            or not np.isfinite(net_return.to_numpy(dtype=float)).all()
        ):
            missing.append(f"{path}:finite returns on unique in-window dates")
            continue
        frame = frame.assign(net_return=net_return)
        returns[asset] = frame.set_index("date")["net_return"].astype(float)
    return (returns if not missing else None), missing


def _block_mean_pvalue(
    differences: np.ndarray,
    *,
    block_size: int,
    samples: int,
    seed: int,
) -> float:
    """Two-sided moving-block test for a zero mean paired-return difference."""
    values = np.asarray(differences, dtype=float)
    if len(values) < block_size:
        raise ValueError("paired return series is shorter than one bootstrap block")
    observed = abs(float(values.mean()))
    centered = values - values.mean()
    rng = np.random.default_rng(seed)
    starts = np.arange(len(values) - block_size + 1)
    blocks = int(np.ceil(len(values) / block_size))
    extreme = 0
    for _ in range(samples):
        draw = rng.choice(starts, size=blocks, replace=True)
        sample = np.concatenate(
            [centered[index : index + block_size] for index in draw]
        )[: len(values)]
        extreme += abs(float(sample.mean())) >= observed
    return float((extreme + 1) / (samples + 1))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/kdd_factorial.yaml")
    parser.add_argument("--runs-root", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    protocol = config["protocol"]
    assets = list(protocol["assets"])
    weights = {key: float(value) for key, value in protocol["capital_weights"].items()}
    seeds = [int(value) for value in protocol["seeds"]]
    arms = list(config["arms"])
    root = Path(args.runs_root)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)

    status: dict[str, Any] = {"config": args.config, "runs": {}}
    portfolio_returns: dict[tuple[str, int], pd.Series] = {}
    for arm in arms:
        status["runs"][arm] = {}
        for seed in seeds:
            run_dir = root / arm / f"seed_{seed}"
            asset_returns, missing = _load_run(
                run_dir, arm, seed, assets, protocol
            )
            if missing:
                status["runs"][arm][str(seed)] = {
                    "status": "missing",
                    "missing": missing,
                }
                continue

            audit, metrics = synchronized_portfolio(
                asset_returns,
                weights,
                PortfolioConfig(initial_capital=float(protocol["initial_capital"])),
            )
            metrics["sharpe_bootstrap"] = moving_block_bootstrap_sharpe(
                audit["portfolio_return"].to_numpy(),
                block_size=int(protocol["bootstrap_block_days"]),
                samples=int(protocol["bootstrap_samples"]),
                seed=seed,
            )
            run_output = output / arm / f"seed_{seed}"
            run_output.mkdir(parents=True, exist_ok=True)
            pd.concat(asset_returns, axis=1, join="inner").to_csv(
                run_output / "asset_daily_pnl.csv", index_label="date"
            )
            audit.to_csv(run_output / "portfolio_daily_pnl.csv", index_label="date")
            (run_output / "portfolio_metrics.json").write_text(
                json.dumps(metrics, indent=2), encoding="utf-8"
            )
            portfolio_returns[(arm, seed)] = audit["portfolio_return"]
            status["runs"][arm][str(seed)] = {
                "status": "complete",
                "n_days": len(audit),
            }

    comparisons: dict[str, Any] = {}
    for seed in seeds:
        full = portfolio_returns.get(("full", seed))
        if full is None:
            continue
        raw: dict[str, float] = {}
        for arm in arms:
            if arm == "full" or (arm, seed) not in portfolio_returns:
                continue
            paired = pd.concat(
                [full, portfolio_returns[(arm, seed)]], axis=1, join="inner"
            ).dropna()
            raw[arm] = _block_mean_pvalue(
                (paired.iloc[:, 0] - paired.iloc[:, 1]).to_numpy(),
                block_size=int(protocol["bootstrap_block_days"]),
                samples=int(protocol["bootstrap_samples"]),
                seed=seed,
            )
        if raw:
            comparisons[str(seed)] = {
                "raw_p": raw,
                "holm_adjusted_p": holm_adjust(raw),
            }
    status["comparisons_vs_full"] = comparisons
    missing_count = sum(
        record["status"] == "missing"
        for arm in status["runs"].values()
        for record in arm.values()
    )
    status["summary"] = {
        "expected_runs": len(arms) * len(seeds),
        "missing_runs": missing_count,
        "proxy_results_used": False,
    }
    (output / "factorial_status.json").write_text(
        json.dumps(status, indent=2), encoding="utf-8"
    )
    if args.strict and missing_count:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
