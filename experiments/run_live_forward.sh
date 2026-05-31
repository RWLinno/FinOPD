#!/bin/bash
set -euo pipefail
# Stage 6: Live-Forward Daemon
cd "$(dirname "$0")/.."
export PYTHONPATH="src:${PYTHONPATH:-}"
eval "$(conda shell.bash hook)"
conda activate finopd
export ALL_PROXY=http://accelerator-cname-hnpmnhnmdul3rmxrwhgend.c.vegalb.com:80

TICKERS="AAPL MSFT NVDA GOOGL AMZN JPM GS V UNH JNJ WMT KO MCD XOM CVX"

echo "=== Live-Forward Inference ==="
echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"

python -m finvl.eval.rigor.live_forward \
    --config configs/default.yaml \
    --tickers $TICKERS \
    --output outputs/live_forward/ \
    --date "$(date +%Y-%m-%d)"

echo "=== Live-Forward Complete ==="
echo "Results: outputs/live_forward/$(date +%Y-%m-%d).json"
