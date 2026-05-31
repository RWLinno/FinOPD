#!/bin/bash
set -euo pipefail
# Stage 6: Generate Final Report + Upload to HuggingFace
cd "$(dirname "$0")/.."
export PYTHONPATH="src:${PYTHONPATH:-}"
eval "$(conda shell.bash hook)"
conda activate finopd
export ALL_PROXY=http://accelerator-cname-hnpmnhnmdul3rmxrwhgend.c.vegalb.com:80
export HF_TOKEN=${HF_TOKEN}

echo "=== Generate Final Report ==="
echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"

python scripts/generate_report.py \
    --experiments-dir outputs/experiments/ \
    --baselines-dir outputs/experiments/ \
    --evolution-curve outputs/opsd_full/evolution_curve.jsonl \
    --live-forward-dir outputs/live_forward/ \
    --output outputs/final_report.html

echo "[Report] outputs/final_report.html"

# Upload checkpoints and data to HuggingFace
echo "=== Uploading to HuggingFace ==="

if [ -d "outputs/vlm_lora" ]; then
    echo "Uploading VLM LoRA checkpoint..."
    huggingface-cli upload RWLinno/FinOPD-VLM-LoRA outputs/vlm_lora/ || true
fi

if [ -d "outputs/opsd_full" ]; then
    echo "Uploading OPSD checkpoints..."
    huggingface-cli upload RWLinno/FinOPD-Checkpoints outputs/opsd_full/ || true
fi

if [ -d "data/chart_geometry" ]; then
    echo "Uploading ChartGeometry dataset..."
    huggingface-cli upload RWLinno/FinChartGeometry-50K data/chart_geometry/ --repo-type dataset || true
fi

echo "=== Report & Upload Complete ==="
