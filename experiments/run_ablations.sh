#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH="src:${PYTHONPATH:-}"
DATA="${1:-data/processed/csi300_daily.csv}"
echo "Running ablation suite..."
python scripts/run_ablation.py --config configs/default.yaml --data "$DATA" --output-dir outputs/experiments "${@:2}"
echo "Done."
