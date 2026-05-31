#!/bin/bash
set -euo pipefail
# Stage 4: Evolution Curve Logging and Visualization
cd "$(dirname "$0")/.."
export PYTHONPATH="src:${PYTHONPATH:-}"
eval "$(conda shell.bash hook)"
conda activate finopd

echo "=== Evolution Curve Analysis ==="
echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"

python -c "
import sys, json
sys.path.insert(0, 'src')
from finvl.self_evolution.curves.logger import EvolutionLogger
from pathlib import Path

logger = EvolutionLogger()
curve_path = 'outputs/opsd_full/evolution_curve.jsonl'

if Path(curve_path).exists():
    logger.load(curve_path)
    print(f'Loaded {logger.num_iterations} iterations')
    print(f'Monotonically improving: {logger.is_monotonically_improving()}')
    
    for r in logger.records:
        print(json.dumps(r, indent=2))
else:
    print(f'Evolution curve not found at {curve_path}')
    print('Run OPSD full training first.')
"

echo "=== Evolution Curve Analysis Complete ==="
