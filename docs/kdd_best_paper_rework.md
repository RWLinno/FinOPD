# KDD review-to-evidence revision record

This file maps every major review concern to an implementation, manuscript
change, or an explicit missing-evidence status. No absent experiment is
represented by a proxy.

| Review concern | Action | Evidence/status |
| --- | --- | --- |
| W1 model-weight contamination | Replaced “strict post-cutoff” with “retrospective point-in-time”; withheld financial claims and required a true-forward window. | Addressed in wording; forward evidence missing. |
| W2 macro-average mislabeled as portfolio | Removed 60.9/1.41/3.30 from the active claims; added synchronized capital-weighted PnL evaluator. | Evaluator implemented; Qwen3.5 PnL missing. |
| W3 one path/seed and no uncertainty | Locked seeds 42/123/456, 20-day moving-block bootstrap, paired tests, and Holm correction. | Protocol implemented; 27 runs missing. |
| W4 mechanism not isolated | Added nine-arm OPD × memory × credit × KL × router × execution matrix. | Fail-closed aggregator implemented; runs missing. |
| W5 central quantities undefined | Aligned utility, five-scalar teacher schema, full-vocabulary JSD/KL, measured reference KL, recorded router mask, state signatures, JSON output bounds, rollback, and memory chronology with code. | Code, tests, and method synchronized. |
| W6 data/baseline/selection audit | Require run manifests, exact checkpoint, finite per-asset daily returns, common weights/costs/delay, and no development proxies. | Contract implemented; baseline runs missing. |

## Architecture corrections

- Four upstream agents are deterministic structured evidence modules. They do
  not all generate Qwen tokens.
- Qwen3.5-9B is the sole deployable token policy; Qwen3.5-27B is a frozen
  post-horizon teacher.
- Coalition replay records five role contributions, but only the positive
  DecisionPM credit weight scales the final policy-token loss.
- Router input is the MAD-normalized current 157-factor state, not a pooled VLM
  embedding. Online updates reuse the rollout's deterministic top-15 mask.
- Episodic retrieval uses a deterministic return/volume signature and filters
  by outcome `available_date` before similarity search.
- Unsupported RASW, regime-dependent thresholds, adaptive turnover,
  trend-break protection, encoder compute, and latency claims were removed.
- Three old figures encoding those unsupported mechanisms/results were removed
  from the manuscript.

## Verified implementation evidence

- Frozen artifact: 157 records; 157 finite on the audit slice; 121 non-constant;
  content-addressed binary only.
- Router: ordered manifest restored from checkpoint and exactly 15 factor IDs
  selected in smoke evaluation.
- Memory: future outcome episodes are excluded; hit rate counts successful
  queries rather than returned neighbors.
- Trainer: real rollout → utility → same-horizon coalition replay → positive
  credit → 9B update → recorded-mask router update → measured KL → accept/revert
  → memory admission.
- Factorial evaluator: 27 expected arm/seed runs; empty audit reports 27 missing
  and `proxy_results_used=false`.

## Intentionally unresolved

- No synchronized Qwen3.5 portfolio PnL or positive financial result exists in
  the repository yet.
- No held-out factorial arm, multi-seed effect estimate, block-bootstrap
  interval, or Holm-adjusted comparison can be reported yet.
- The paper is non-anonymous by explicit project instruction; this does not
  resolve a venue rule if KDD ultimately requires double-blind submission.
