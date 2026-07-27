#!/bin/bash
set -euo pipefail
# ============================================================
# FinOPD Full Experiment Pipeline - 一键式执行
# 按依赖链顺序执行所有实验，收集结果并写入 LaTeX 表格
# 使用: bash experiments/run_full_pipeline.sh [--quick]
# ============================================================
cd "$(dirname "$0")/.."
export PYTHONPATH="src:${PYTHONPATH:-}"

# Load credentials from .env
if [ -f .env ]; then
  set -a; source .env; set +a
fi
export ALL_PROXY=${ALL_PROXY:-http://accelerator-cname-hnpmnhnmdul3rmxrwhgend.c.vegalb.com:80}
export NO_PROXY=localhost,127.0.0.1
export no_proxy=localhost,127.0.0.1
export OPENAI_API_KEY=${OPENAI_API_KEY:-EMPTY}
export WANDB_PROJECT=${WANDB_PROJECT:-finopd}
export CUDA_VISIBLE_DEVICES=0,1

QUICK=false
MAX_DATES=50
TICKERS="AAPL MSFT NVDA GOOGL AMZN JPM GS V UNH JNJ WMT KO MCD XOM CVX HD DIS CRM CSCO IBM VZ NKE PG MRK BA"
SEEDS="42 123 456"

while [[ $# -gt 0 ]]; do
  case $1 in
    --quick) QUICK=true; MAX_DATES=20; TICKERS="AAPL MSFT NVDA JPM GS"; SEEDS="42"; shift;;
    --max-dates) MAX_DATES="$2"; shift 2;;
    *) shift;;
  esac
done

TS=$(date +%Y%m%d_%H%M%S)
LOG_DIR="logs/pipeline_${TS}"
RESULTS_DIR="outputs/experiments/pipeline_${TS}"
mkdir -p "$LOG_DIR" "$RESULTS_DIR"

echo "============================================================"
echo "FinOPD Full Pipeline - ${TS}"
echo "Mode: $([ "$QUICK" = true ] && echo 'QUICK' || echo 'FULL')"
echo "Tickers: $(echo $TICKERS | wc -w)"
echo "Max dates: ${MAX_DATES}"
echo "Seeds: ${SEEDS}"
echo "============================================================"

# ===== Stage 1: Start vLLM Server =====
echo ""
echo "[Stage 1] Starting vLLM server..."
if ! curl -s http://localhost:8000/v1/models >/dev/null 2>&1; then
  eval "$(conda shell.bash hook)" && conda activate finopd
  nohup python -m vllm.entrypoints.openai.api_server \
    --model "${FINOPD_STUDENT_MODEL:-.models/Qwen3.5-9B}" \
    --tensor-parallel-size 1 \
    --trust-remote-code \
    --max-model-len 4096 \
    --port 8000 --host 0.0.0.0 \
    > "${LOG_DIR}/vllm_server.log" 2>&1 &
  VLLM_PID=$!
  echo "  Waiting for vLLM to load (PID: $VLLM_PID)..."
  for i in $(seq 1 60); do
    sleep 10
    if curl -s http://localhost:8000/v1/models >/dev/null 2>&1; then
      echo "  vLLM ready after ${i}0 seconds"
      break
    fi
  done
else
  echo "  vLLM already running"
fi

# ===== Stage 2: Factor Router Training =====
echo ""
echo "[Stage 2] Training Factor Router..."
if [ ! -f "outputs/router/router_best.pt" ]; then
  python3 -m finvl.factors.train_router \
    --data data/processed/us_dow30.csv \
    --asset AAPL \
    --factor-artifact src/finvl/factors/frozen_factors.bin \
    --output outputs/router/ \
    --epochs 30 --top-k 15 --max-samples 1000 \
    > "${LOG_DIR}/router_train.log" 2>&1
  echo "  Router trained: outputs/router/router_best.pt"
else
  echo "  Router already trained, skipping"
fi

# ===== Stage 3: Main Experiments (per ticker, per seed) =====
echo ""
echo "[Stage 3] Running main experiments..."
for SEED in $SEEDS; do
  echo "  Seed: $SEED"
  for TICKER in $TICKERS; do
    OUT="${RESULTS_DIR}/main_seed${SEED}/${TICKER}"
    python3 scripts/run_experiment.py \
      --config configs/default.yaml \
      --data data/processed/us_dow30.csv \
      --asset "$TICKER" \
      --seed "$SEED" \
      --output-dir "$OUT" \
      --max-dates "$MAX_DATES" \
      > "${LOG_DIR}/main_${TICKER}_s${SEED}.log" 2>&1
    SR=$(grep "sharpe_ratio" "${LOG_DIR}/main_${TICKER}_s${SEED}.log" | grep -v no_cost | awk '{print $NF}')
    echo "    ${TICKER}: SR=${SR}"
  done
done

# ===== Stage 4: Ablation Experiments =====
echo ""
echo "[Stage 4] Running ablation experiments..."
ABLATION_OUT="${RESULTS_DIR}/ablations"
mkdir -p "$ABLATION_OUT"

# Run every declared component ablation through the same evaluator.
python3 scripts/run_ablation.py \
  --config configs/default.yaml \
  --data data/processed/us_dow30.csv \
  --asset AAPL \
  --output-dir "$ABLATION_OUT" \
  --max-dates "$MAX_DATES" \
  > "${LOG_DIR}/ablations.log" 2>&1
echo "  Ablation suite done"

# ===== Stage 5: Collect Results & Update LaTeX =====
echo ""
echo "[Stage 5] Collecting results..."
python3 - "$RESULTS_DIR" "$LOG_DIR" << 'PYEOF'
import json, os, sys
import numpy as np
from pathlib import Path

results_dir = sys.argv[1] if len(sys.argv) > 1 else os.environ.get('RESULTS_DIR', 'outputs/experiments')
log_dir = sys.argv[2] if len(sys.argv) > 2 else os.environ.get('LOG_DIR', 'logs')

# Collect main results
all_metrics = {}
main_dir = Path(results_dir) / "main_seed42"
if main_dir.exists():
    for ticker_dir in main_dir.iterdir():
        if ticker_dir.is_dir():
            for sub in ticker_dir.iterdir():
                metrics_file = sub / "metrics.json"
                if metrics_file.exists():
                    metrics = json.loads(metrics_file.read_text())
                    all_metrics[ticker_dir.name] = metrics

if all_metrics:
    srs = [m.get('sharpe_ratio', 0) for m in all_metrics.values()]
    wrs = [m.get('win_rate', 0) for m in all_metrics.values()]
    print(f"\n=== Macro-averaged per-asset results (not a portfolio) ===")
    print(f"Tickers: {len(all_metrics)}")
    print(f"Mean SR: {np.mean(srs):.4f} +/- {np.std(srs):.4f}")
    print(f"Mean WR: {np.mean(wrs):.4f}")
    print(f"Positive SR: {sum(1 for s in srs if s > 0)}/{len(srs)}")

    # Save summary
    summary = {
        'per_ticker': {k: v for k, v in all_metrics.items()},
        'macro_average': {
            'mean_SR': float(np.mean(srs)),
            'std_SR': float(np.std(srs)),
            'mean_WR': float(np.mean(wrs)),
            'positive_ratio': f"{sum(1 for s in srs if s > 0)}/{len(srs)}",
        }
    }
    with open(Path(results_dir) / 'final_summary.json', 'w') as f:
        json.dump(summary, f, indent=2)
    print(f"Saved: {results_dir}/final_summary.json")
PYEOF

# Runtime claims must be derived from command logs or an external profiler.
# The pipeline deliberately emits no hard-coded efficiency numbers.
echo "[Stage 6] Efficiency: use measured wall-time/GPU profiler logs; no proxy emitted."

echo ""
echo "============================================================"
echo "Pipeline complete! Results: ${RESULTS_DIR}"
echo "Logs: ${LOG_DIR}"
echo "============================================================"
