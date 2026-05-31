#!/bin/bash
# ============================================================
# FinOPD Experiment Dashboard - 实验总看板
# 更新时间: 2026-06-01
# 依赖链: S0 → S1 → S2 → S3(MVP) → S4(OPSD) → S5(Main) → S6(Report)
# 仓库: GitHub RWLinno/FinOPD (branch: exp_May28)
# 监控: wandb.ai/finopd | HuggingFace: RWLinno/FinOPD-*
# ============================================================
#
# 一键执行: bash experiments/run_full_pipeline.sh [--quick]
# 可视化:   python -m finvl.gui.dashboard
#
# ============================================================
mkdir -p logs

echo "========== FinOPD Experiment Dashboard =========="
echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"
echo "Branch: $(git branch --show-current 2>/dev/null || echo 'unknown')"
echo ""

# ===== Stage 0: Environment Setup =====
# 状态: DONE (2026-05-28)
# 环境: base conda (PyTorch 2.10) + memagent (vLLM 0.8.2)
# 符号链接: finopd -> memagent
nohup bash experiments/run_env_setup.sh > ./logs/run_env_setup.log 2>&1 &

# ===== Stage 1: Data Infrastructure =====
# 状态: DONE (2026-05-28)
# 产物: data/processed/us_dow30.csv (52775行)
#        data/chart_geometry/train.jsonl (2375样本)
#        data/chart_geometry/swift_train.jsonl (ms-swift格式)
nohup bash experiments/run_data_pipeline.sh > ./logs/run_data_pipeline.log 2>&1 &
nohup bash experiments/run_chart_geometry_build.sh > ./logs/run_chart_geometry_build.log 2>&1 &

# ===== Stage 2: VLM Service + Factor Infrastructure =====
# 状态: DONE (2026-05-30)
# VLM: Qwen2.5-VL-32B-Instruct via vLLM 0.8.2, TP=4, 4xA800
# 因子: DSL Engine 118/157 可计算, Factor Router 30 epochs trained
# 关键修复: VLM parser (//注释, trailing comma), PatternReasoner (名称归一化)
nohup bash experiments/run_vlm_lora_train.sh > ./logs/run_vlm_lora_train.log 2>&1 &
nohup bash experiments/run_vlm_lora_eval.sh > ./logs/run_vlm_lora_eval.log 2>&1 &

# ===== Stage 3: Factor Router + MVP =====
# 状态: DONE (2026-05-31) | v6 最终版本
# 结果: Mean SR=+0.82, 5/5 tickers 正 Sharpe
#   AAPL: SR=0.46  MSFT: SR=0.51  NVDA: SR=0.73
#   JPM:  SR=1.12  GS:   SR=1.26
# 关键修复: Backtest HOLD逻辑, 仓位30%, 非对称阈值, DSL因子接入
nohup bash experiments/run_factor_router_train.sh > ./logs/run_factor_router_train.log 2>&1 &
nohup bash experiments/run_mvp.sh > ./logs/run_mvp.log 2>&1 &

# ===== Stage 4: Self-Evolution (OPSD + Belief) =====
# 状态: PENDING (需额外GPU时间, 每轮4小时)
# 预期: SR 从 0.82 提升到 1.2-1.5
nohup bash experiments/run_opsd_stability.sh > ./logs/run_opsd_stability.log 2>&1 &
nohup bash experiments/run_opsd_full.sh > ./logs/run_opsd_full.log 2>&1 &
nohup bash experiments/run_belief_consolidation.sh > ./logs/run_belief_consolidation.log 2>&1 &
nohup bash experiments/run_evolution_curve.sh > ./logs/run_evolution_curve.log 2>&1 &

# ===== Stage 5: Main Experiments & Ablations =====
# 状态: PARTIAL (v6结果可用, 全量待跑)
nohup bash experiments/run_main.sh > ./logs/run_main.log 2>&1 &
nohup bash experiments/run_ablations.sh > ./logs/run_ablations.log 2>&1 &
nohup bash experiments/run_baselines.sh > ./logs/run_baselines.log 2>&1 &
nohup bash experiments/run_counterfactual.sh > ./logs/run_counterfactual.log 2>&1 &
nohup bash experiments/run_regime_analysis.sh > ./logs/run_regime_analysis.log 2>&1 &

# ===== Stage 6: Report + Upload =====
# 状态: PARTIAL (GUI dashboard 已实现)
nohup bash experiments/run_live_forward.sh > ./logs/run_live_forward.log 2>&1 &
nohup bash experiments/generate_report.sh > ./logs/generate_report.log 2>&1 &

echo ""
echo "=== 当前最佳结果 (v6) ==="
echo "Mean Sharpe Ratio: 0.82 (5/5 tickers positive)"
echo "Model: Qwen2.5-VL-32B-Instruct + 118 evolved factors"
echo "Factor Router: Gumbel-Softmax top-15, trained 30 epochs"
echo ""
echo "=== 快速命令 ==="
echo "一键全流程: bash experiments/run_full_pipeline.sh --quick"
echo "可视化面板: python -m finvl.gui.dashboard"
echo "查看结果:   cat outputs/experiments/v6_*/*/metrics.json"
echo ""
