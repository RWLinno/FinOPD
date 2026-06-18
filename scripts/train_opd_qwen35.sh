#!/bin/bash
# Train OPD LoRA on Qwen3.5-9B with ms-swift (per Qwen3.5 best practice).
# Multimodal SFT: candlestick chart image + time-series text -> <think>reasoning</think> + JSON decision.
# Uses CoT-augmented data so the thinking model emits reasoning then the JSON answer.
#
# Usage:
#   bash scripts/train_opd_qwen35.sh dryrun   # smoke test
#   bash scripts/train_opd_qwen35.sh full     # full training
set -e

ENV_PY=/Knowin/foundation/weilinruan/envs/qwen35/bin
export PATH=$ENV_PY:$PATH
cd /Knowin/foundation/weilinruan/FinOPD

MODE=${1:-dryrun}
MODEL=/Knowin/foundation/models/Qwen/Qwen3.5-9B
DATA=data/opd_train_v2/opd_multimodal_cot.jsonl   # CoT-augmented for thinking model
OUT=outputs/opd_lora_qwen35_v3

export IMAGE_MAX_TOKEN_NUM=1024
export VIDEO_MAX_TOKEN_NUM=128
export FPS_MAX_FRAMES=12
export PYTORCH_CUDA_ALLOC_CONF='expandable_segments:True'
export NPROC_PER_NODE=3
export CUDA_VISIBLE_DEVICES=5,6,7

if [ "$MODE" = "dryrun" ]; then
  EXTRA="--max_steps 6 --dataset ${DATA}#50"
  OUT=${OUT}_dryrun
  ATTN=sdpa
else
  EXTRA="--num_train_epochs 2 --dataset ${DATA}"
  ATTN=${ATTN:-flash_attention_2}
fi

swift sft \
  --model $MODEL \
  --tuner_type lora \
  $EXTRA \
  --load_from_cache_file true \
  --split_dataset_ratio 0.01 \
  --torch_dtype bfloat16 \
  --per_device_train_batch_size 2 \
  --per_device_eval_batch_size 2 \
  --learning_rate 1e-4 \
  --lora_rank 32 \
  --lora_alpha 64 \
  --target_modules all-linear \
  --freeze_vit true \
  --freeze_aligner true \
  --gradient_accumulation_steps 4 \
  --group_by_length true \
  --output_dir $OUT \
  --eval_steps 200 \
  --save_steps 200 \
  --save_total_limit 2 \
  --logging_steps 5 \
  --max_length 2048 \
  --warmup_ratio 0.05 \
  --dataset_num_proc 4 \
  --dataloader_num_workers 4 \
  --deepspeed zero2 \
  --attn_impl $ATTN
