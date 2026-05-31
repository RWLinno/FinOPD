#!/bin/bash
set -euo pipefail
# Stage 1: Data Pipeline - Download Dow-30 + CSI300 OHLCV data
cd "$(dirname "$0")/.."
export PYTHONPATH="src:${PYTHONPATH:-}"
source ~/.bashrc
eval "$(conda shell.bash hook)"
conda activate finopd
export ALL_PROXY=http://accelerator-cname-hnpmnhnmdul3rmxrwhgend.c.vegalb.com:80

echo "=== FinOPD Data Pipeline ==="
echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"

# Dow-30 tickers (25 representative)
DOW30_TICKERS="AAPL MSFT NVDA GOOGL AMZN JPM GS V UNH JNJ WMT KO MCD XOM CVX HD DIS CRM CSCO IBM VZ NKE PG MRK BA"

# CSI300 subset (high-liquidity, via tushare codes)
CSI300_CODES="600519 601318 600036 000858 601012 600276 000333 002415 601888 600900 000001 601166 600030 002304 600887"

mkdir -p data/processed data/raw

echo "[1/3] Downloading Dow-30 OHLCV (2018-01 to 2026-05)..."
python scripts/prepare_data.py download \
    --tickers $DOW30_TICKERS \
    --start 2018-01-01 \
    --end 2026-05-28 \
    --output-dir data/raw

echo "[2/3] Building Dow-30 combined dataset..."
for TICKER in $DOW30_TICKERS; do
    if [ -f "data/raw/${TICKER}_ohlcv.csv" ]; then
        python scripts/prepare_data.py build \
            --ohlcv-path "data/raw/${TICKER}_ohlcv.csv" \
            --asset "$TICKER" \
            --market US \
            --lookback 60 \
            --sample-every 1 \
            --start 2019-01-01 \
            --output-dir "data/processed/${TICKER}" \
            --split train
    fi
done

echo "[3/3] Merging per-asset CSVs..."
python -c "
import pandas as pd
import os
from pathlib import Path

raw_dir = Path('data/raw')
tickers = '$DOW30_TICKERS'.split()
frames = []
for t in tickers:
    p = raw_dir / f'{t}_ohlcv.csv'
    if p.exists():
        df = pd.read_csv(p, parse_dates=True, index_col=0)
        df['ticker'] = t
        frames.append(df)
if frames:
    combined = pd.concat(frames)
    combined.to_csv('data/processed/us_dow30.csv')
    print(f'Combined {len(frames)} tickers, {len(combined)} rows -> data/processed/us_dow30.csv')
"

echo "=== Data Pipeline Complete ==="
