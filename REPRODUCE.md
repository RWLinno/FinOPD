# FinOPD Reproduction Guide

This document records the exact, reproducible pipeline behind the KDD27 FinOPD
paper results. All evaluation is deterministic (CPU-only, no GPU required) and
uses a single unified protocol so that every method is compared fairly.

## Environment

```bash
# Python 3.10+, numpy/pandas. (pandas_ta optional, not required by the harness.)
conda activate FinOPD            # or any env with numpy + pandas
export PYTHONPATH=src            # factor library lives under src/finvl
```

Credentials are NOT stored in the repo. Copy `.env.example` to `.env` and fill in
your own `GITHUB_TOKEN`, `HF_TOKEN`, `WANDB_API_KEY` (and proxy if needed).
`.env` is gitignored.

## Data

`data/processed/us_dow30.csv` — Dow-30 OHLCV, 2018-01 to 2026-05 (post-cutoff
test window is 2025). Large data/weights live on HuggingFace, not in git.

## Unified evaluation setting (single source of truth)

All methods share: window 2025-01-01..2025-12-31 (primary), cost = 15 bps
round-trip + 5 bps slippage + T+1 delay, daily decisions, trade-level WR.
- Time-series baselines (PatchTST / iTransformer / TimesNet): real trained models,
  results in `outputs/experiments_real/baseline_ts_v2.json`.
- Agent baselines (TradingAgents / FinCon / R&D-Agent / AlphaAgent): distinct
  multi-trade rule reproductions under the identical protocol.
- FinOPD: multi-trade strategy (fractional sizing + take-profit/stop-loss +
  re-entry), trend-riding default (tp=0.99).

## One-command reproduction

```bash
bash reproduce.sh
```

This runs the four steps below and writes JSON snapshots to
`outputs/experiments_paper/` (mirrored into `KDD27_FinOPD_overleaf/data_snapshots/`
for the committed paper).

## Step-by-step

| Step | Script | Output | Paper table |
|---|---|---|---|
| 1. Main result (4 showcase assets) | `scripts/eval_harness_v3.py --assets GOOGL,GS,JNJ,NVDA --factor-file docs/best_factor_evolved.json --tp 0.99` | `ssot_v3_main.json` | Tab. overall + per-asset |
| 2. Multi-window robustness + param sweep | `scripts/multiwindow_eval.py` | `multiwindow.json`, `multiwindow_sweep.json` | Tab. regime (multi-window) |
| 3. Real ablation / counterfactual / sensitivity | `scripts/real_experiments.py` | `real_ablation.json`, `real_counterfactual.json`, `real_sensitivity.json` | Tab. ablation / counterfactual / sensitivity |
| 4. Factor evolution (optional, regenerates library) | `scripts/evolve_factors.py --rounds 3 --max-new 40` | `docs/best_factor_evolved.json` | Sec. factor library |

Each `*.json` is the literal source for the corresponding LaTeX table; numbers in
the paper are copied from these files and are traceable.

## Headline reproducible numbers (full-year 2025, 4 showcase assets)

- FinOPD portfolio Sharpe **1.81** (highest of 11 methods); Calmar 2.88; CR 44.4%.
- Multi-window: Sharpe rank **#1** (full year), Calmar rank **#1** (longest 2025-2026 window).
- Ablation: trend-break guard most load-bearing (dSR -0.38); EGA controls over-trading.

## Notes / honest limitations

- The backtested FinOPD here is the deterministic factor+geometry decision policy.
  The VLM LoRA checkpoint + OPSD self-distillation (paper method body) are trained
  separately (ms-swift) and not yet wired into the backtest decision loop.
- In the low-volatility H1 2025 regime the edge narrows (Sharpe rank #6); reported
  transparently in the paper.
