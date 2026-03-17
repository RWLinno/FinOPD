#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH="src:${PYTHONPATH:-}"
DATA="${1:-data/processed/csi300_daily.csv}"
OUT="outputs/experiments/regime_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$OUT"
echo "Running regime analysis..."
python -c "
import sys,json,numpy as np,pandas as pd
sys.path.insert(0,'src')
from finvl.data.schema import validate_ohlcv_df
from finvl.evaluation.analysis import RegimeAnalyzer
from finvl.evaluation.metrics import compute_all_metrics
df=pd.read_csv('${DATA}',parse_dates=True,index_col=0)
df=validate_ohlcv_df(df)
ra=RegimeAnalyzer(); reg=ra.classify_dates(df,window=20)
c=df['close'].values; r=np.diff(c)/c[:-1]
res=ra.regime_conditioned_metrics(r,df.index[1:],reg)
for regime,m in sorted(res.items()):
    print(f'{regime:20s} Sharpe={m.get(\"sharpe_ratio\",0):>8.4f}  Days={m.get(\"num_days\",0):>5d}')
with open('${OUT}/regime_results.json','w') as f: json.dump(res,f,indent=2,default=str)
"
echo "Done. Results: ${OUT}/"
