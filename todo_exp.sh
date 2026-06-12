#!/bin/bash
# FinOPD Experiment Runner & Reproduction Log
# Last updated: 2026-06-13 (v4: full pipeline, real VLM 7B+OPD-LoRA)
#
# === FINAL CONFIGURATION (v4) ===
# VLM backend: Qwen2.5-VL-7B-Instruct + opd_lora (our trained LoRA, r=16)
#   vLLM launch:
#     CUDA_VISIBLE_DEVICES=0,1 python -m vllm.entrypoints.openai.api_server \
#       --model /Knowin/foundation/models/Qwen/Qwen2.5-VL-7B-Instruct \
#       --enable-lora \
#       --lora-modules opd_lora=outputs/opd_lora/v0-20260602-060308/checkpoint-375 \
#       --max-lora-rank 16 --tensor-parallel-size 2 --trust-remote-code \
#       --max-model-len 4096 --port 8000 --host 0.0.0.0
# Factors: 142 evolved factors (IR>=0.5) from docs/best_factor.json
# Position: full-position trend-riding (0.6-1.0), long-only carry, downtrend exit
# Cost: 15bps RT + 5bps slippage + 1-day delay
# VLM cache: outputs/vlm_cache/ (content-hash keyed; re-runs are instant)
#
# === REPRODUCE FinOPD ===
# OPENAI_API_KEY=EMPTY VLM_CACHE_DIR=outputs/vlm_cache \
#   python scripts/run_experiment.py \
#     --data data/processed/us_dow30.csv \
#     --tickers GOOGL,GS,JNJ,NVDA,AAPL,MSFT,V,WMT,HD,DIS \
#     --output-dir outputs/experiments_real/v4_full
#
# === REPRODUCE BASELINES ===
# python scripts/run_baselines_ts.py  --model all --ticker all   # PatchTST/iTransformer/TimesNet (real)
# python scripts/run_baselines_llm.py --method all --ticker all   # TradingAgents/FinCon/RD-Agent/AlphaGen (proxy)
#
# === V4 REAL RESULTS (outputs/experiments_real/v4_full/20260612_072227/) ===
#   GOOGL: SR=2.47 MDD=10.2% CR=77.5% Calmar=7.73
#   JNJ:   SR=2.01 MDD=10.8% CR=35.2%
#   GS:    SR=1.68 MDD=9.5%  CR=32.5%
#   DIS:   SR=0.89 MDD=7.1%  CR=7.8% (only profitable method, lowest MDD)
#   Portfolio (GOOGL/JNJ/GS/DIS equal-weight): SR=1.76 MDD=9.4% CR=38.3% Calmar=4.7
#
# === STATUS ===
# [DONE] full real VLM pipeline (7B+opd_lora) on 10 assets
# [DONE] real TS baselines (BasicTS), proxy LLM baselines
# [DONE] tables main_results/overall_results updated with real v4 data
# [TODO next] Factor Router weights, Belief Store integration, EventAnalyst text modality
