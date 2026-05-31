#!/bin/bash
set -euo pipefail
# Stage 5: Counterfactual Perturbation Analysis
cd "$(dirname "$0")/.."
export PYTHONPATH="src:${PYTHONPATH:-}"
eval "$(conda shell.bash hook)"
conda activate finopd
export ALL_PROXY=http://accelerator-cname-hnpmnhnmdul3rmxrwhgend.c.vegalb.com:80
export CUDA_VISIBLE_DEVICES=0

echo "=== Counterfactual Perturbation Analysis ==="
echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"

python -m finvl.eval.rigor.counterfactual \
    --config configs/default.yaml \
    --data data/processed/us_dow30.csv \
    --output outputs/counterfactual/ \
    --max-dates 100 \
    --seeds 42 123 456

echo "=== Counterfactual Analysis Complete ==="
echo "Results: outputs/counterfactual/"
