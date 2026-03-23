#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

export PYTHONPATH="src:${PYTHONPATH:-}"

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-7860}"
SHARE="${SHARE:-false}"

export FINVL_GUI_HOST="$HOST"
export FINVL_GUI_PORT="$PORT"
export FINVL_GUI_SHARE="$SHARE"

echo "[FinVL-MAS] Launching GUI with python: $(which python)"
python - <<'PY2'
import importlib.util as u, sys
missing=[]
for m in ['gradio','plotly']:
    if u.find_spec(m) is None:
        missing.append(m)
if missing:
    print('[FinVL-MAS] Missing GUI deps:', ', '.join(missing))
    print('[FinVL-MAS] Install with: pip install gradio plotly')
    sys.exit(1)
print('[FinVL-MAS] GUI dependencies OK')
PY2

echo "[FinVL-MAS] Dashboard bind: ${HOST}:${PORT} (share=${SHARE})"
echo "[FinVL-MAS] Local URL on server: http://127.0.0.1:${PORT}"
python -m finvl.gui.app
