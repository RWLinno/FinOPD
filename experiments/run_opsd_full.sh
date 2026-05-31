#!/bin/bash
set -euo pipefail
# Stage 4: OPSD Full Training (all Dow-30 assets, 8 iterations)
cd "$(dirname "$0")/.."
export PYTHONPATH="src:${PYTHONPATH:-}"
eval "$(conda shell.bash hook)"
conda activate finopd
export ALL_PROXY=http://accelerator-cname-hnpmnhnmdul3rmxrwhgend.c.vegalb.com:80
export WANDB_PROJECT=FinOPD
export WANDB_API_KEY=${WANDB_API_KEY}
export HF_TOKEN=${HF_TOKEN}
export CUDA_VISIBLE_DEVICES=0,1,2,3

ASSETS="AAPL MSFT NVDA GOOGL AMZN JPM GS V UNH JNJ WMT KO MCD XOM CVX HD DIS CRM CSCO IBM VZ NKE PG MRK BA"

echo "=== OPSD Full Training ==="
echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"

python -m finvl.self_evolution.opsd.train \
    --config configs/opsd.yaml \
    --model /Knowin/foundation/weilinruan/hf_models/Qwen/Qwen2.5-VL-32B-Instruct \
    --lora-path outputs/vlm_lora/ \
    --assets $ASSETS \
    --iterations 8 \
    --output outputs/opsd_full/ \
    --seeds 42 123 456 \
    --wandb_run opsd_full

echo "=== OPSD Full Training Complete ==="
