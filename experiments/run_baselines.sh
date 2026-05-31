#!/usr/bin/env bash
set -euo pipefail
# Stage 5: Run all baselines (12 methods)
cd "$(dirname "$0")/.."
export PYTHONPATH="src:${PYTHONPATH:-}"
eval "$(conda shell.bash hook)"
conda activate finopd
export ALL_PROXY=http://accelerator-cname-hnpmnhnmdul3rmxrwhgend.c.vegalb.com:80
export WANDB_PROJECT=FinOPD
export WANDB_API_KEY=${WANDB_API_KEY}
export CUDA_VISIBLE_DEVICES=0,1

DATA="${1:-data/processed/us_dow30.csv}"
OUT="outputs/experiments/baselines_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$OUT"
SEEDS="42 123 456"

echo "=== Running All Baselines ==="
echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"
echo "Data: ${DATA}"

python scripts/run_baselines_full.py \
    --data "$DATA" \
    --output-dir "$OUT" \
    --seeds $SEEDS \
    --config configs/default.yaml

echo "=== Baselines Complete ==="
echo "Results: ${OUT}/"
