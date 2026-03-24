#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH="src:${PYTHONPATH:-}"
RDIR="${1:-outputs/experiments}"
OUTPUT="${2:-outputs/report.html}"
echo "Generating report from ${RDIR}..."
python -c "
import sys,json,glob,os
sys.path.insert(0,'src')
from finvl.visualization.report import generate_report
rd='${RDIR}'; out='${OUTPUT}'
metrics={}
for mf in glob.glob(os.path.join(rd,'**/metrics.json'),recursive=True):
    with open(mf) as f: metrics=json.load(f); break
ablation={}
for af in glob.glob(os.path.join(rd,'**/ablation_results.json'),recursive=True):
    with open(af) as f: ablation=json.load(f); break
if not metrics: print('No metrics found.'); sys.exit(0)
p=generate_report(metrics=metrics,ablation_results=ablation or None,output_path=out)
print(f'Report: {p}')
"
echo "Done."
