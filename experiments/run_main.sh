#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH="src:${PYTHONPATH:-}"
DATA="${1:-data/processed/csi300_daily.csv}"
OUT="outputs/experiments/main_$(date +%Y%m%d_%H%M%S)"
echo "Running main experiment... Data: ${DATA}"
python scripts/run_experiment.py --config configs/default.yaml --data "$DATA" --output-dir "$OUT" "${@:2}"
echo "Done. Results: ${OUT}/"
