#!/bin/bash
set -euo pipefail
# FinOPD Environment Setup
# 创建 conda 环境、安装依赖、配置凭证

echo "=== FinOPD Environment Setup ==="
echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"

# Network proxy
export ALL_PROXY=http://accelerator-cname-hnpmnhnmdul3rmxrwhgend.c.vegalb.com:80

# Create conda environment
if ! conda info --envs | grep -q "finopd"; then
    echo "[1/5] Creating conda environment..."
    conda create -n finopd python=3.10 -y
else
    echo "[1/5] Conda env 'finopd' already exists, skipping."
fi

# Activate and install dependencies
echo "[2/5] Installing dependencies..."
eval "$(conda shell.bash hook)"
conda activate finopd

pip install -e ".[all]"
pip install ms-swift[all] vllm faiss-gpu wandb yfinance tushare pandas_ta
pip install transformers accelerate peft bitsandbytes
pip install patchtst timesnet  # baseline models if available

# Configure credentials
echo "[3/5] Configuring credentials..."
cat > .env <<'EOF'
HF_TOKEN=${HF_TOKEN}
WANDB_API_KEY=${WANDB_API_KEY}
EOF

export HF_TOKEN=${HF_TOKEN}
export WANDB_API_KEY=${WANDB_API_KEY}

# Wandb login
wandb login --relogin "$WANDB_API_KEY" || true

# HuggingFace login
huggingface-cli login --token "$HF_TOKEN" || true

# Git branch setup
echo "[4/5] Setting up git branch..."
git checkout v3 2>/dev/null || true
git checkout -b exp_May28 2>/dev/null || git checkout exp_May28 2>/dev/null || true

# Create output directories
echo "[5/5] Creating directory structure..."
mkdir -p data/processed data/raw data/chart_geometry
mkdir -p outputs/experiments outputs/vlm_lora outputs/router
mkdir -p outputs/opsd_stability outputs/opsd_full outputs/belief_store
mkdir -p outputs/counterfactual outputs/live_forward
mkdir -p logs

echo "=== Setup Complete ==="
