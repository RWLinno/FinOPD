#!/bin/bash
set -euo pipefail
# Stage 3: MVP End-to-End Run (without self-evolution)
cd "$(dirname "$0")/.."
export PYTHONPATH="src:${PYTHONPATH:-}"
eval "$(conda shell.bash hook)"
conda activate finopd
export ALL_PROXY=http://accelerator-cname-hnpmnhnmdul3rmxrwhgend.c.vegalb.com:80
export WANDB_PROJECT=FinOPD
export WANDB_API_KEY=${WANDB_API_KEY}
export HF_TOKEN=${HF_TOKEN}
export CUDA_VISIBLE_DEVICES=0,1,2,3

SEEDS="42 123 456"
EXP_NAME="mvp"
OUTPUT_BASE="outputs/experiments/$(date +%Y-%m-%d)_${EXP_NAME}"

echo "=== MVP End-to-End Run ==="
echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"

for SEED in $SEEDS; do
    echo "--- Seed: $SEED ---"
    python scripts/run_experiment.py \
        --config configs/default.yaml \
        --data data/processed/us_dow30.csv \
        --output-dir "${OUTPUT_BASE}/seed_${SEED}" \
        --max-dates 250
done

echo "=== MVP Complete ==="
echo "Results: ${OUTPUT_BASE}/"
