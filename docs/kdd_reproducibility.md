# KDD reproduction contract

This branch reproduces the Qwen3.5 implementation, not the archived Qwen2.5
financial tables. The only trainable token policy is Qwen3.5-9B; four
deterministic specialists provide structured evidence. A frozen Qwen3.5-27B
teacher is available only after an outcome horizon closes and receives five
scalars: utility, cumulative return, maximum drawdown, CVaR loss, and turnover.
No hosted model or factor API is part of the evidence path.

## Evidence levels

- Unit audits validate deterministic contracts such as finite factor execution,
  ordered router IDs, and availability-filtered retrieval.
- Component smoke tests load real local checkpoints and exercise generation or
  one optimizer step. They are not financial results.
- A financial result exists only when an arm/seed has a matching
  `run_manifest.json`, a resolvable checkpoint, and finite cost-adjusted daily
  returns for all four locked assets.

The current branch has component evidence but no complete Qwen3.5 financial
arm. Values 60.9/1.41/3.30 were archived arithmetic means of per-asset metrics,
not synchronized portfolio statistics, and are excluded from the active paper.

## Frozen factor artifact

The 157 factors are packaged in
`src/finvl/factors/frozen_factors.bin`. The mutable research JSON/JSONL is not
published, and no factor-serving endpoint is required. The artifact SHA-256 is
recorded in `configs/factor_artifact.yaml`. Router checkpoints store the same
ordered factor names, so weights cannot silently bind to a permuted manifest.

At inference, every factor is evaluated on the current trailing window. The
157-value vector is median/MAD normalized, clipped, padded to 768, and joined
with a four-way regime one-hot. The router deterministically selects 15 IDs.
During online update it reuses that recorded mask with standardized matured
utility and entropy regularization; it does not resample an action.

## Time-safe memory

The retrieval signature is deterministic: up to 60 close returns concatenated
with 60 within-window volume z-scores, padded and normalized to 768 dimensions.
Every episode carries `available_date`, the end of its outcome horizon. Queries
first filter to `available_date <= as_of_date`, then retrieve by cosine
similarity. Memory admission occurs only after a policy/router update passes the
measured reference-KL guard.

## Locked financial matrix

`configs/kdd_factorial.yaml` declares nine mechanism arms, seeds 42/123/456,
AAPL/GOOGL/NVDA/JPM, equal 25% capital weights, USD 1,000,000 initial capital,
15 bps transaction cost, 5 bps slippage, and one-day execution delay.

Run:

```bash
PYTHONPATH=src python scripts/run_kdd_factorial.py \
  --config configs/kdd_factorial.yaml \
  --runs-root <runs> \
  --output <audit-output> \
  --strict
```

Relative checkpoint paths resolve against the arm/seed directory. Each
`daily_returns.csv` must have unique in-window dates and finite `net_return`.
The evaluator inner-aligns asset dates, writes asset and synchronized portfolio
daily PnL, recomputes portfolio metrics, adds a fixed-seed 20-day moving-block
Sharpe interval, performs paired block tests against full, and applies Holm
correction. Missing arms remain `missing`; proxies are never emitted.

## Temporal scope

January 2025--May 2026 can only be called a retrospective point-in-time window.
Qwen3.5 postdates its start, so runtime input discipline does not exclude
knowledge in model weights. A stronger claim requires a true-forward window
after the model/data cutoff and contamination controls such as ticker masking,
date-token masking, and text-free inputs.
