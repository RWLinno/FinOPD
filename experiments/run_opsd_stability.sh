#!/bin/bash
set -euo pipefail
# Stage 4: OPSD Stability Check (single asset AAPL, 3 epochs)
cd "$(dirname "$0")/.."
export PYTHONPATH="src:${PYTHONPATH:-}"
eval "$(conda shell.bash hook)"
conda activate finopd
export ALL_PROXY=http://accelerator-cname-hnpmnhnmdul3rmxrwhgend.c.vegalb.com:80
export WANDB_PROJECT=FinOPD
export WANDB_API_KEY=${WANDB_API_KEY}
export HF_TOKEN=${HF_TOKEN}
export CUDA_VISIBLE_DEVICES=0,1,2,3

echo "=== OPSD Stability Check ==="
echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"

python -m finvl.self_evolution.opsd.train \
    --config configs/opsd.yaml \
    --model /Knowin/foundation/weilinruan/hf_models/Qwen/Qwen2.5-VL-32B-Instruct \
    --lora-path outputs/vlm_lora/ \
    --assets AAPL \
    --iterations 3 \
    --output outputs/opsd_stability/ \
    --wandb_run opsd_stability

echo "=== OPSD Stability Check Complete ==="
