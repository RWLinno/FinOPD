#!/bin/bash
set -euo pipefail
# Stage 5: Regime-Conditioned Analysis
cd "$(dirname "$0")/.."
export PYTHONPATH="src:${PYTHONPATH:-}"
eval "$(conda shell.bash hook)"
conda activate finopd
export ALL_PROXY=http://accelerator-cname-hnpmnhnmdul3rmxrwhgend.c.vegalb.com:80
export CUDA_VISIBLE_DEVICES=0,1

echo "=== Regime-Conditioned Analysis ==="
echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"

python -c "
import sys, json, numpy as np, pandas as pd
from pathlib import Path
sys.path.insert(0, 'src')
from finvl.core.config import load_config
from finvl.data.provider import OHLCVProvider
from finvl.evaluation.metrics import sharpe_ratio

cfg = load_config('configs/default.yaml')
data_path = 'data/processed/us_dow30.csv'

if not Path(data_path).exists():
    print('Data not found. Run data pipeline first.')
    exit(0)

df = pd.read_csv(data_path, parse_dates=True, index_col=0)
if 'ticker' in df.columns:
    df = df[df['ticker'] == df['ticker'].unique()[0]]

# Classify regimes
returns = df['close'].pct_change().fillna(0)
vol_20 = returns.rolling(20).std() * np.sqrt(252)
slope_60 = df['close'].pct_change(60)

regimes = pd.Series('normal', index=df.index)
regimes[vol_20 < vol_20.quantile(0.25)] = 'calm'
regimes[vol_20 > vol_20.quantile(0.75)] = 'volatile'
regimes[(slope_60 > 0.1) & (regimes == 'normal')] = 'trending'
regimes[(slope_60.abs() < 0.03) & (regimes == 'normal')] = 'ranging'

# Report regime distribution
print('Regime distribution:')
print(regimes.value_counts())

# Compute per-regime returns (placeholder for full system)
for regime in ['calm', 'normal', 'volatile', 'trending', 'ranging']:
    mask = regimes == regime
    regime_returns = returns[mask].values
    if len(regime_returns) > 10:
        sr = sharpe_ratio(regime_returns)
        print(f'  {regime:12s}: SR={sr:.4f} (n={len(regime_returns)})')

output_dir = Path('outputs/experiments/regime_analysis')
output_dir.mkdir(parents=True, exist_ok=True)
results = {'regimes': regimes.value_counts().to_dict()}
with open(output_dir / 'regime_results.json', 'w') as f:
    json.dump(results, f, indent=2, default=str)
print(f'Results saved to {output_dir}')
"

echo "=== Regime Analysis Complete ==="
