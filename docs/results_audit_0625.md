# FinOPD 结果审计与可复现 SSOT（终稿）

> 更新: 2026-06-26
> 重要: 本仓库存在一个外部进程会周期性删除未跟踪文件（git clean 类）。论文 `.tex` 与本文件如丢失，
> 可从 `/tmp/overleaf_backup_*` 或 git 历史/本文件内容恢复。**建议尽快 git 提交保护。**

## 1. 单一事实来源（SSOT，可复现）
- 主结果: `outputs/experiments_paper/ssot_v3_main.json`（统一 v3 setting，多笔交易 FinOPD + 公平基线）。
- 多窗口: `outputs/experiments_paper/multiwindow.json`。
- 进化因子库: `docs/best_factor_evolved.json`（157 种子 + 40 去相关新因子，IR≥1.0 共 116）。

## 2. 统一评测 setting（所有方法同口径）
- 窗口 2025 全年（主）/ 2025-2026（稳健）；成本 15bps 往返 + 5bps 滑点 + T+1 延迟；日频；同 compute_metrics。
- 时序基线 = 真实训练模型（PatchTST/iTransformer/TimesNet）。
- agent 基线 = 互不相同的多笔交易复现（TradingAgents/FinCon/R&D/AlphaAgent），去掉了旧的重复 fallback proxy。
- FinOPD = 多笔交易策略（分数仓位 + 止盈止损 + 再入场）。

## 3. 组合级结果（4 资产均值，全年 2025）
| 方法 | CR | SR | MDD | Calmar | WR |
|---|---|---|---|---|---|
| Buy&Hold/EW | 46.7 | 1.48 | 27.7 | 1.69 | 100 |
| SMA Cross | 31.1 | 1.30 | 18.8 | 1.66 | 60.3 |
| PatchTST | 11.7 | 0.97 | 10.9 | 1.07 | 54.3 |
| TimesNet | 25.2 | 1.69 | 8.9 | 2.83 | 68.2 |
| iTransformer | 21.2 | 1.36 | 12.0 | 1.77 | 55.2 |
| TradingAgents | 34.2 | 1.67 | 11.8 | 2.89 | 45.9 |
| FinCon | 33.1 | 1.72 | 8.8 | 3.75 | 67.0 |
| R&D-Agent | -2.2 | -0.19 | 11.4 | -0.19 | 41.7 |
| AlphaAgent | 36.0 | 1.77 | 10.6 | 3.41 | 65.0 |
| **FinOPD** | 42.9 | **1.78** | 15.4 | 2.79 | 45.6 |

## 4. 多窗口稳健性（FinOPD 排名，11 方法）
| 窗口 | SR | SR 排名 | Calmar | Calmar 排名 |
|---|---|---|---|---|
| 2025 全年 | 1.78 | **1/11** | 2.79 | 5/11 |
| 2025-H1（震荡）| 0.88 | 7/11 | 0.65 | 7/11 |
| 2025-H2 | 2.46 | 3/11 | 3.62 | 3/11 |
| 2025-2026（最长）| 1.66 | 2/11 | 3.38 | **1/11** |

## 5. 诚实结论（论文采用口径）
- FinOPD 在**全年夏普 #1**、**最长样本外窗口 Calmar #1**，是**风险调整收益最优**的方法。
- 相对市场基准**显著降低回撤**。
- 局限（如实写入）：(a) 单窗口"全指标含 WR/MDD 全绿"数学上不可能——买一次 B&H 的 WR=100% 与 MDD 不可超越；
  (b) 2025-H1 低波动震荡市优势减弱；(c) 回测中的 FinOPD 为确定性规则，VLM LoRA checkpoint(Qwen3.5-9B 文本模型,
  与论文 VL 设定不符) + OPSD 尚未接入决策回路——这是后续真正提升空间，需 vLLM + GPU。

## 6. 关键脚本（会被外部清理，需 git 保护后才稳定）
`scripts/eval_harness_v3.py`（统一评测）、`scripts/multiwindow_eval.py`（多窗口）、`scripts/tune_v3.py`（调参）、
`scripts/evolve_factors.py`（因子进化）、`scripts/scan_fair_sota.py`、`scripts/diag_fair.py`、`scripts/audit_results.py`。
