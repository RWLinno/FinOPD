# KDD best-paper revision record

This report is deliberately outside the manuscript.

## Scientific changes

- Reframed the contribution around a temporal information contract rather than
  an unsupported first-ever claim.
- Defined one executable outcome utility with return, drawdown, CVaR, and
  turnover weights; the same value now controls routing, memory admission, and
  coalition credit.
- Replaced the undefined unordered top-k likelihood with the implemented
  straight-through advantage-weighted surrogate.
- Distinguished the deployable Qwen3.5-9B student from the training-only frozen
  Qwen3.5-27B teacher and the round-start 9B reference.
- Renamed the hindsight ``ceiling'' as a privileged diagnostic policy; it is not
  claimed to be a mathematical upper bound.
- Added an information/update contract table and explicitly classified the
  evaluation as retrospective point-in-time because model-weight contamination
  cannot be excluded.

## Artifact changes

- Removed fixed-return trajectory scoring; outcome utility now uses realized
  close-to-close returns, T+1 positions, 15 bps cost, 5 bps slippage, drawdown,
  CVaR, and turnover.
- Made multi-asset providers require an explicit ticker, preventing duplicate
  dates from different assets from entering one lookback window.
- Removed noisy heuristic Shapley and random placeholder teacher logits.
  Evidence-bearing runs now fail fast unless a deterministic coalition evaluator
  and the real teacher runtime are present.
- Retained the content-addressed 157-factor artifact and synchronized portfolio
  evaluator introduced earlier on the branch.

## Claims intentionally not added

- No fabricated multi-seed, confidence-interval, factorial-ablation, or
  portfolio-PnL result was inserted.
- Existing 60.9/1.41/3.30 numbers remain labeled as macro-averaged per-asset
  summaries, not synchronized portfolio metrics.
- The paper does not claim a live, strict post-cutoff, or contamination-free
  evaluation.
