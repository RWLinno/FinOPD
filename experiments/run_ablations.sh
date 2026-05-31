#!/usr/bin/env bash
set -euo pipefail
# Stage 5: Full Ablation Suite (A1-A10)
cd "$(dirname "$0")/.."
export PYTHONPATH="src:${PYTHONPATH:-}"
eval "$(conda shell.bash hook)"
conda activate finopd
export ALL_PROXY=http://accelerator-cname-hnpmnhnmdul3rmxrwhgend.c.vegalb.com:80
export WANDB_PROJECT=FinOPD
export WANDB_API_KEY=${WANDB_API_KEY}
export CUDA_VISIBLE_DEVICES=0,1,2,3

DATA="${1:-data/processed/us_dow30.csv}"
SEEDS="42 123 456"

echo "=== Full Ablation Suite (A1-A10) ==="
echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"

# A1: Full FinOPD (baseline for comparison)
# A2-A8: Existing ablation configs
python scripts/run_ablation.py \
    --config configs/default.yaml \
    --data "$DATA" \
    --max-dates 250 \
    --output-dir outputs/experiments

# A9: Single iteration (k=1)
echo "--- A9: Single Iteration ---"
python scripts/run_experiment.py \
    --config configs/ablations/single_iteration.yaml \
    --data "$DATA" \
    --output-dir outputs/experiments/ablation_A9_single_iter

# A10: Trajectory search (replace OPSD)
echo "--- A10: Trajectory Search ---"
python scripts/run_experiment.py \
    --config configs/ablations/trajectory_search.yaml \
    --data "$DATA" \
    --output-dir outputs/experiments/ablation_A10_traj_search

echo "=== Ablation Suite Complete ==="
