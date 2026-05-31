#!/bin/bash
set -euo pipefail
# Stage 2: VLM LoRA Evaluation
cd "$(dirname "$0")/.."
export PYTHONPATH="src:${PYTHONPATH:-}"
eval "$(conda shell.bash hook)"
conda activate finopd
export ALL_PROXY=http://accelerator-cname-hnpmnhnmdul3rmxrwhgend.c.vegalb.com:80
export CUDA_VISIBLE_DEVICES=0

echo "=== VLM LoRA Evaluation ==="
echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"

python scripts/eval_vlm_lora.py \
    --model /Knowin/foundation/weilinruan/hf_models/Qwen/Qwen2.5-VL-32B-Instruct \
    --lora-path outputs/vlm_lora/ \
    --test-data data/chart_geometry/train.jsonl \
    --output outputs/vlm_lora_eval.json \
    --max-samples 500

echo "=== VLM LoRA Evaluation Complete ==="
echo "Results: outputs/vlm_lora_eval.json"
