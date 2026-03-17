#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH="src:${PYTHONPATH:-}"
echo "Launching FinVL-MAS Dashboard on http://localhost:7860 ..."
python -m finvl.gui.app
