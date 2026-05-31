#!/bin/bash
set -euo pipefail
# Stage 4: Belief Consolidation (non-parametric track)
cd "$(dirname "$0")/.."
export PYTHONPATH="src:${PYTHONPATH:-}"
eval "$(conda shell.bash hook)"
conda activate finopd
export ALL_PROXY=http://accelerator-cname-hnpmnhnmdul3rmxrwhgend.c.vegalb.com:80
export WANDB_PROJECT=FinOPD
export WANDB_API_KEY=${WANDB_API_KEY}
export HF_TOKEN=${HF_TOKEN}
export CUDA_VISIBLE_DEVICES=0,1,2,3

echo "=== Belief Consolidation ==="
echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"

# Belief consolidation runs as part of OPSD but can also be run standalone
python -c "
import sys
sys.path.insert(0, 'src')
from finvl.self_evolution.belief.index import BeliefIndex
from finvl.self_evolution.belief.extractor import BeliefExtractor
import json, numpy as np

# Load trajectories from OPSD output and build belief store
belief_index = BeliefIndex(capacity=10000, embedding_dim=768)
extractor = BeliefExtractor()

# Check if OPSD has produced trajectory data
import os
opsd_dir = 'outputs/opsd_full/'
if os.path.exists(opsd_dir):
    for iter_dir in sorted(os.listdir(opsd_dir)):
        store_path = os.path.join(opsd_dir, iter_dir, 'belief_store')
        if os.path.exists(store_path):
            belief_index.load(store_path)
            print(f'Loaded beliefs from {store_path}: {belief_index.size} entries')

belief_index.save('outputs/belief_store/')
print(f'Final belief store: {belief_index.size} entries')
print(f'Hit rate: {belief_index.hit_rate:.4f}')
"

echo "=== Belief Consolidation Complete ==="
echo "Output: outputs/belief_store/"
