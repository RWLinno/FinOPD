#!/usr/bin/env bash
# One-command reproduction of the FinOPD KDD27 paper results (CPU-only, deterministic).
# Usage: bash reproduce.sh
set -euo pipefail

export PYTHONPATH="${PYTHONPATH:-}:src"
PY="${PY:-python}"
OUT="outputs/experiments_paper"
SNAP="KDD27_FinOPD_overleaf/data_snapshots"
mkdir -p "$OUT" "$SNAP"

echo "[1/4] Main result (4 showcase assets, full-year 2025) ..."
$PY scripts/eval_harness_v3.py \
    --assets GOOGL,GS,JNJ,NVDA \
    --factor-file docs/best_factor_evolved.json \
    --tp 0.99 --sl 0.08 --base-entry 0.05 --add-entry 0.15 \
    --output "$OUT/ssot_v3_main.json"

echo "[2/4] Multi-window robustness + parameter sweep ..."
$PY scripts/multiwindow_eval.py

echo "[3/4] Real ablation / counterfactual / sensitivity ..."
$PY scripts/real_experiments.py

echo "[4/4] (optional) Factor evolution -- skip if best_factor_evolved.json exists"
if [ ! -f docs/best_factor_evolved.json ]; then
    $PY scripts/evolve_factors.py --rounds 3 --max-new 40
fi

echo "Mirroring JSON snapshots into the committed paper directory ..."
cp -f "$OUT"/ssot_v3_main.json "$OUT"/multiwindow.json "$OUT"/multiwindow_sweep.json \
      "$OUT"/real_ablation.json "$OUT"/real_counterfactual.json "$OUT"/real_sensitivity.json \
      "$SNAP"/ 2>/dev/null || true

echo "Done. See $SNAP/ for the canonical result JSONs used by the paper tables."
