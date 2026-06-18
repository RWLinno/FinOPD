#!/bin/bash
# Deploy Qwen3.5-9B + OPD LoRA as an OpenAI-compatible API server via ms-swift.
# Uses the pt (transformers) backend (vllm>=0.17 is incompatible with driver 535).
set -e
ENV_BIN=/Knowin/foundation/weilinruan/envs/qwen35/bin
export PATH=$ENV_BIN:$PATH
cd /Knowin/foundation/weilinruan/FinOPD

export IMAGE_MAX_TOKEN_NUM=1024
export PYTORCH_CUDA_ALLOC_CONF='expandable_segments:True'
export CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-5}

ADAPTER=${ADAPTER:-outputs/opd_lora_qwen35_v3/v0-best/checkpoint-best}
PORT=${PORT:-8001}

swift deploy \
  --adapters opd_lora=$ADAPTER \
  --infer_backend pt \
  --torch_dtype bfloat16 \
  --max_new_tokens 256 \
  --served_model_name opd_lora \
  --port $PORT \
  --host 0.0.0.0
