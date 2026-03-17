#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH="src:${PYTHONPATH:-}"
DATA="${DATA_PATH:-data/processed/csi300_daily.csv}"
TS=$(date +%Y%m%d_%H%M%S)
OUT="outputs/experiments"
MAX_DATES=""
while [[ $# -gt 0 ]]; do
  case $1 in
    --data) DATA="$2"; shift 2;;
    --quick) MAX_DATES="--max-dates 30"; shift;;
    *) shift;;
  esac
done
echo "=== FinVL-MAS Paper Experiments ${TS} ==="
echo "[1/4] Main experiment..."
python scripts/run_experiment.py --config configs/default.yaml --data "$DATA" --output-dir "${OUT}/main_${TS}" $MAX_DATES 2>/dev/null || echo "  skipped (data not found)"
echo "[2/4] Ablation suite..."
python scripts/run_ablation.py --config configs/default.yaml --data "$DATA" --output-dir "$OUT" $MAX_DATES 2>/dev/null || echo "  skipped"
echo "[3/4] Paper tables..."
python scripts/generate_paper_assets.py --results-dir "${OUT}/main_${TS}" --output-dir papers/tables 2>/dev/null || echo "  skipped"
echo "[4/4] Done. Results: ${OUT}/"
