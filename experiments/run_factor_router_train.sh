#!/bin/bash
set -euo pipefail
# Stage 3: Factor Router Training
cd "$(dirname "$0")/.."
export PYTHONPATH="src:${PYTHONPATH:-}"
eval "$(conda shell.bash hook)"
conda activate finopd
export ALL_PROXY=http://accelerator-cname-hnpmnhnmdul3rmxrwhgend.c.vegalb.com:80
export WANDB_PROJECT=FinOPD
export WANDB_API_KEY=${WANDB_API_KEY}
export HF_TOKEN=${HF_TOKEN}
export CUDA_VISIBLE_DEVICES=0

echo "=== Factor Router Training ==="
echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"

python -m finvl.factors.train_router \
    --factor-artifact src/finvl/factors/frozen_factors.bin \
    --data data/processed/us_dow30.csv \
    --asset AAPL \
    --output outputs/router/ \
    --epochs 20 \
    --lr 1e-3 \
    --batch-size 64 \
    --top-k 15

echo "=== Factor Router Training Complete ==="
