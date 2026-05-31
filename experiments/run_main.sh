#!/usr/bin/env bash
set -euo pipefail
# Stage 5: Main Experiment (Full FinOPD on Dow-30 test set)
cd "$(dirname "$0")/.."
export PYTHONPATH="src:${PYTHONPATH:-}"
eval "$(conda shell.bash hook)"
conda activate finopd
export ALL_PROXY=http://accelerator-cname-hnpmnhnmdul3rmxrwhgend.c.vegalb.com:80
export WANDB_PROJECT=FinOPD
export WANDB_API_KEY=${WANDB_API_KEY}
export CUDA_VISIBLE_DEVICES=0,1,2,3

DATA="${1:-data/processed/us_dow30.csv}"
SEEDS="42 123 456"
EXP_NAME="main"
OUTPUT_BASE="outputs/experiments/$(date +%Y-%m-%d)_${EXP_NAME}"

echo "=== Main Experiment (Full FinOPD) ==="
echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"
echo "Data: ${DATA}"

for SEED in $SEEDS; do
    echo "--- Seed: $SEED ---"
    python scripts/run_experiment.py \
        --config configs/default.yaml \
        --data "$DATA" \
        --output-dir "${OUTPUT_BASE}/seed_${SEED}"
done

echo "=== Main Experiment Complete ==="
echo "Results: ${OUTPUT_BASE}/"
