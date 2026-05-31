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
export CUDA_VISIBLE_DEVICES=0,1,2,3

echo "=== Factor Router Training ==="
echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"

python -m finvl.factors.train_router \
    --factor_lib docs/best_factor.json \
    --data data/chart_geometry/train.jsonl \
    --output outputs/router/ \
    --epochs 20 \
    --lr 1e-3 \
    --batch-size 64 \
    --top-k 15 \
    --wandb_run router_train

echo "=== Factor Router Training Complete ==="
