# Resource Links / 资源登记

All large artifacts (data, weights) live on HuggingFace; only code, paper, and
small result JSONs are in git. Credentials are never committed (see `.env.example`).

## GitHub
- Repo: https://github.com/RWLinno/FinOPD
- Branch: `exp_0626` (paper + reproducible scripts + result snapshots)

## HuggingFace
- Dataset (OHLCV + result JSON snapshots): https://huggingface.co/datasets/rwlinno/FinOPD-data
  - `processed/us_dow30.csv`, `processed/cn_csi300.csv`
  - `results/*.json` (ssot_v3_main, multiwindow, real_ablation/counterfactual/sensitivity, baselines)
- LoRA adapter (Qwen3.5-9B OPD): https://huggingface.co/rwlinno/FinOPD-lora
  - `lora/checkpoint-988/` (adapter weights; optimizer states excluded)

## Weights & Biases
- Project: `finopd` — training curves for the OPD LoRA self-evolution runs.

## How to pull large artifacts
```bash
pip install huggingface_hub
huggingface-cli download rwlinno/FinOPD-data --repo-type dataset --local-dir data/
huggingface-cli download rwlinno/FinOPD-lora --local-dir outputs/lora/
```

## Reproduce
See `REPRODUCE.md`. One command: `bash reproduce.sh` (CPU-only, deterministic).
