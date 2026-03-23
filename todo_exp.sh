#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"
mkdir -p logs experiments/logs

source "/root/miniconda3/etc/profile.d/conda.sh"
conda activate finvl-mas

DATA_PATH="${DATA_PATH:-data/processed/synth_daily.csv}"
MAX_DATES="${MAX_DATES:-60}"

setup_env() {
  echo "[setup] install project + deps in finvl-mas"
  python -m pip install -e .
  python -m pip install gradio plotly matplotlib mplfinance
}

smoke_test() {
  echo "[smoke] compile"
  python -m compileall src scripts

  echo "[smoke] quick main"
  bash experiments/run_main.sh "$DATA_PATH" --max-dates 5

  echo "[smoke] baseline"
  bash experiments/run_baselines.sh "$DATA_PATH"

  echo "[smoke] ablation quick"
  bash experiments/run_ablations.sh "$DATA_PATH" --max-dates 10

  echo "[smoke] regime"
  bash experiments/run_regime_analysis.sh "$DATA_PATH"

  echo "[smoke] run_all quick"
  bash experiments/run_all.sh --data "$DATA_PATH" --quick

  echo "[smoke] gui build"
  python - <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, str(Path('src')))
from finvl.gui.app import create_app
create_app()
print('GUI create_app OK')
PY
}

run_nohup_jobs() {
  echo "[run] launching background jobs"
  nohup bash experiments/run_main.sh "$DATA_PATH" --max-dates "$MAX_DATES" > ./logs/run_main.log 2>&1 &
  nohup bash experiments/run_baselines.sh "$DATA_PATH" > ./logs/run_baselines.log 2>&1 &
  nohup bash experiments/run_ablations.sh "$DATA_PATH" --max-dates "$MAX_DATES" > ./logs/run_ablations.log 2>&1 &
  nohup bash experiments/run_regime_analysis.sh "$DATA_PATH" > ./logs/run_regime_analysis.log 2>&1 &
  nohup bash experiments/run_all.sh --data "$DATA_PATH" --quick > ./logs/run_all.log 2>&1 &
  echo "[run] launched. check logs/run_*.log"
}

action_gui() {
  echo "[gui] launching dashboard in background"
  nohup bash experiments/launch_gui.sh > ./logs/run_gui.log 2>&1 &
  echo "[gui] launched. check logs/run_gui.log"
}

show_help() {
  cat <<USAGE
Usage: bash todo_exp.sh [setup|smoke|run|gui|all]

setup : install dependencies in conda env finvl-mas
smoke : run foreground end-to-end quick checks
run   : start nohup experiment jobs and write logs/run_*.log
gui   : start GUI in background and write logs/run_gui.log
all   : setup + smoke + run

Env overrides:
  DATA_PATH=<path>   default: data/processed/synth_daily.csv
  MAX_DATES=<int>    default: 60
USAGE
}

CMD="${1:-all}"
case "$CMD" in
  setup) setup_env ;;
  smoke) smoke_test ;;
  run) run_nohup_jobs ;;
  gui) action_gui ;;
  all)
    setup_env
    smoke_test
    run_nohup_jobs
    ;;
  *)
    show_help
    exit 1
    ;;
esac
