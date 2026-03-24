#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH="src:${PYTHONPATH:-}"
DATA="${1:-data/processed/csi300_daily.csv}"
OUT="outputs/experiments/baselines_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$OUT"
echo "Running baselines on ${DATA}..."
python - <<PY2
import sys, json, numpy as np, pandas as pd
sys.path.insert(0, 'src')
from finvl.data.schema import validate_ohlcv_df
from finvl.evaluation.metrics import compute_all_metrics

df = pd.read_csv('${DATA}', parse_dates=True, index_col=0)
df = validate_ohlcv_df(df)
close = df['close'].values.astype(float)
if len(close) < 30:
    raise ValueError('Need at least 30 bars for baselines')

returns = np.diff(close) / close[:-1]
bh = compute_all_metrics(returns)
bh['strategy'] = 'Buy-and-Hold'

s5 = pd.Series(close).rolling(5, min_periods=1).mean().values
s20 = pd.Series(close).rolling(20, min_periods=1).mean().values
signal = np.where(s5[:-1] > s20[:-1], 1.0, -1.0)
signal[:20] = 0.0
strat_returns = signal * returns
sm = compute_all_metrics(strat_returns)
sm['strategy'] = 'SMA-5/20'

res = {'Buy-and-Hold': bh, 'SMA-Crossover': sm}
with open('${OUT}/baseline_results.json', 'w') as f:
    json.dump(res, f, indent=2, default=str)

for name, m in res.items():
    print(f"{name:20s} Sharpe={m.get('sharpe_ratio', 0):.4f}  Return={m.get('annualized_return', 0):.2%}")
PY2
echo "Done. Results: ${OUT}/"
