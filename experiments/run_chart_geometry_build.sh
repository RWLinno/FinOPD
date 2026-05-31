#!/bin/bash
set -euo pipefail
# Stage 1: Build ChartGeometry dataset (~50K samples)
cd "$(dirname "$0")/.."
export PYTHONPATH="src:${PYTHONPATH:-}"
eval "$(conda shell.bash hook)"
conda activate finopd
export ALL_PROXY=http://accelerator-cname-hnpmnhnmdul3rmxrwhgend.c.vegalb.com:80

echo "=== ChartGeometry Dataset Build ==="
echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"

python scripts/build_chart_geometry.py \
    --data-dir data/raw \
    --output-dir data/chart_geometry \
    --train-start 2015-01-01 \
    --train-end 2022-12-31 \
    --lookback 60 \
    --sample-every 5 \
    --max-samples 60000

echo "=== ChartGeometry Build Complete ==="
echo "Output: data/chart_geometry/train.jsonl"
