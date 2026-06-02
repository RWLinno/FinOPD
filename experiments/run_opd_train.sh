#!/bin/bash
set -euo pipefail
# FinOPD: On-Policy Distillation Training
# Uses ms-swift to fine-tune Qwen2.5-VL-7B with hindsight direction labels
cd "$(dirname "$0")/.."

if [ -f .env ]; then set -a; source .env; set +a; fi
export NO_PROXY=localhost,127.0.0.1
export CUDA_VISIBLE_DEVICES=0,1,2,3
export WANDB_PROJECT=finopd

MODEL_PATH="/Knowin/foundation/weilinruan/hf_models/Qwen/Qwen2.5-VL-7B-Instruct"
DATASET="data/opd_train/opd_train.jsonl"
OUTPUT_DIR="outputs/opd_lora"

echo "=== FinOPD: OPD LoRA Training ==="
echo "Model: ${MODEL_PATH}"
echo "Dataset: ${DATASET} ($(wc -l < ${DATASET}) samples)"
echo "Output: ${OUTPUT_DIR}"
echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

swift sft \
  --model "${MODEL_PATH}" \
  --dataset "${DATASET}" \
  --output_dir "${OUTPUT_DIR}" \
  --lora_rank 16 \
  --lora_alpha 32 \
  --target_modules q_proj v_proj o_proj k_proj \
  --num_train_epochs 3 \
  --per_device_train_batch_size 1 \
  --gradient_accumulation_steps 16 \
  --learning_rate 2e-5 \
  --warmup_ratio 0.05 \
  --max_length 2048 \
  --logging_steps 10 \
  --save_strategy epoch \
  --bf16 true \
  --gradient_checkpointing true \
  --report_to wandb \
  --run_name opd_lora_v1

echo "=== OPD Training Complete ==="
echo "Checkpoint: ${OUTPUT_DIR}"
