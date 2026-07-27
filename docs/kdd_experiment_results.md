# KDD branch verification results

Run date: 2026-07-27. Data: the repository's `us_dow30.csv`, restricted to the
last 500 AAPL bars for the factor execution audit. This is an implementation
test, not an investment-performance claim.

The frozen artifact contains 157 manifest records. All 157 produced finite
outputs after the loader was corrected to preserve duplicate display names and
sanitize non-finite DSL arithmetic. Of these, 121 were non-constant on this
single 500-bar slice; constants are expected when a factor depends on optional
fields absent from the OHLCV-only slice. Artifact SHA-256:
`51c338c93163876fd0a01f8919993e2cfa464032bdced8b2fc55687530c1e550`.

Automated verification: 4 tests passed. Tests cover all 157 factor records,
finite factor outputs, synchronized portfolio construction, the distinction
between portfolio Sharpe and averaged asset Sharpe, undefined zero-exposure
Sharpe, reproducible moving-block bootstrap, and monotone Holm adjustment.

No new return number was manufactured. The positive financial numbers in the
paper remain the archived per-asset results and are now labeled as descriptive
macro-averages. New portfolio or causal-ablation numbers require the locked
daily-PnL protocol in `docs/kdd_reproducibility.md`.
