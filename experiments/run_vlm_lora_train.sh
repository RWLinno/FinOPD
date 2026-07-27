#!/bin/bash
set -euo pipefail
# Stage 2: VLM LoRA Training via ms-swift
cd "$(dirname "$0")/.."
export PYTHONPATH="src:${PYTHONPATH:-}"
eval "$(conda shell.bash hook)"
conda activate finopd
export ALL_PROXY=http://accelerator-cname-hnpmnhnmdul3rmxrwhgend.c.vegalb.com:80
export WANDB_PROJECT=FinOPD
export WANDB_API_KEY=${WANDB_API_KEY}
export HF_TOKEN=${HF_TOKEN}
export CUDA_VISIBLE_DEVICES=0,1,2,3

echo "=== VLM LoRA Training (ms-swift) ==="
echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"

# Step 1: Convert data to ms-swift format
echo "[1/2] Converting data to ms-swift format..."
python scripts/convert_to_swift.py \
    --input data/chart_geometry/train.jsonl \
    --output data/chart_geometry/swift_train.jsonl

# Step 2: Train with ms-swift
echo "[2/2] Starting LoRA training..."
swift sft \
    --model "${FINOPD_STUDENT_MODEL:-.models/Qwen3.5-9B}" \
    --dataset data/chart_geometry/swift_train.jsonl \
    --output_dir outputs/vlm_lora/ \
    --lora_rank 16 \
    --lora_alpha 32 \
    --target_modules q_proj v_proj o_proj \
    --num_train_epochs 3 \
    --per_device_train_batch_size 2 \
    --gradient_accumulation_steps 8 \
    --learning_rate 2e-5 \
    --warmup_ratio 0.05 \
    --max_length 2048 \
    --logging_steps 10 \
    --save_strategy epoch \
    --bf16 true \
    --deepspeed default-zero2 \
    --use_wandb true \
    --wandb_project FinOPD \
    --run_name vlm_lora_train

echo "=== VLM LoRA Training Complete ==="
echo "Checkpoint: outputs/vlm_lora/"
