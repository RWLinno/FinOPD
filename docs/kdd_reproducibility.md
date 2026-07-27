# KDD reproduction contract

The branch separates claims already supported by archived aggregate tables from
claims that require rerunning synchronized daily PnL. The current 60.9/1.41/3.30
table is explicitly a macro-average of per-asset metrics. It is not a portfolio
return series.

For a portfolio claim, export one cost-adjusted daily return CSV per asset and
run `scripts/evaluate_portfolio.py`. The command intersects dates, records each
asset return and weight, retains unallocated cash, and writes both
`portfolio_daily_pnl.csv` and `portfolio_metrics.json`. Sharpe uncertainty uses
a 20-trading-day moving-block bootstrap with a recorded seed. Comparisons across
arms must apply Holm correction.

The locked mechanism matrix is `configs/kdd_factorial.yaml`. Every arm must use
the same data snapshot, dates, seed, model initialization, inference budget,
cost, slippage, delay, and capital weights. Missing arms are reported as missing;
they must never be filled with proxy or simulated results. In particular,
`scripts/run_baselines_full.py` contains development proxies and is excluded
from paper evidence until each method is replaced by its cited implementation.

The deployable geometry encoder, student, and decision agents are pinned to
Qwen3.5-9B, while the training-only frozen hindsight teacher is Qwen3.5-27B in
`configs/opsd.yaml`.
The January 2025--May 2026 study is therefore described as a retrospective
point-in-time backtest, not a live or proven contamination-free evaluation.
Ticker masking, date-token masking, text-free inputs, and weight-cutoff evidence
are required before making a stronger model-contamination claim.

The 157-factor library is packaged as `frozen_factors.bin` and verified by the
SHA-256 digest in `configs/factor_artifact.yaml`. The mutable research JSONL is
intentionally excluded. This preserves deterministic execution on the
reproduction branch without publishing the research manifest as JSON.
