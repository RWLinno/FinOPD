#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH="src:${PYTHONPATH:-}"
DATA="${1:-data/processed/csi300_daily.csv}"
OUT="outputs/experiments/baselines_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$OUT"
echo "Running baselines on ${DATA}..."
python -c "
import sys,json,numpy as np,pandas as pd
sys.path.insert(0,'src')
from finvl.data.schema import validate_ohlcv_df
from finvl.evaluation.metrics import compute_all_metrics
df=pd.read_csv('${DATA}',parse_dates=True,index_col=0)
df=validate_ohlcv_df(df)
c=df['close'].values; r=np.diff(c)/c[:-1]
bh=compute_all_metrics(r); bh['strategy']='Buy-and-Hold'
s5=pd.Series(c).rolling(5).mean().values
s20=pd.Series(c).rolling(20).mean().values
sig=np.where(s5[1:]>s20[1:],1.0,-1.0); sig[:20]=0
sr=sig[:-1]*r[20:]; sm=compute_all_metrics(sr); sm['strategy']='SMA-5/20'
res={'Buy-and-Hold':bh,'SMA-Crossover':sm}
with open('${OUT}/baseline_results.json','w') as f: json.dump(res,f,indent=2,default=str)
for n,m in res.items(): print(f'{n:20s} Sharpe={m.get(\"sharpe_ratio\",0):.4f}  Return={m.get(\"annualized_return\",0):.2%}')
"
echo "Done. Results: ${OUT}/"
