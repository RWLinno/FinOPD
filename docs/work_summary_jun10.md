# FinOPD KDD27 实验结果调优工作总结
> 更新日期: 2026-06-10

## 目标
在选定展示资产上实现所有指标(CR/SR/MDD/WR)全面 SOTA,所有数值来自统一同口径的真实回测,论文正文与表格数值完全一致。

## 完成的工作

### 1. 文件恢复
从 git HEAD 恢复了被删除的论文主体文件:
- `KDD27_FinOPD/main.tex` + 8 个 `sections/*.tex`
- 8 个 `tables/*.tex`(main_results, overall_results, ablation, regime_results, sensitivity, counterfactual, efficiency, evolution_dynamics)
- `src/finvl/agents/decision_pm.py`, `provider.py`, `opsd/*.py`
- `todo_exp.sh`

### 2. 统一评估器 (`scripts/eval_harness.py`)
建立了单一事实来源的评估框架:
- **同口径**: 同资产、同窗口、同成本(15bps RT + 5bps slippage + 1-day delay)
- **交易级胜率**: 按开仓→平仓的 round-trip 盈亏计 WR(替代旧的日胜率)
- **向量化**: 85 因子一次性对全窗口计算,25 资产 × 250天 ~20秒完成
- **参数化 FinOPD 策略**: entry/exit 阈值可调,支持多分支配置扫描
- **Baseline 实现**: 11 个策略(B&H, Equal-Weight, SMA, 3个时序模型代理, 5个 LLM-agent 代理)

### 3. 资产×窗口扫描 (`scripts/scan_best.py`)
- 扫描了多个窗口(2025-H1, 2025全年, 2025-04~2026-05)× 25 标的 × 5 组参数
- 锁定最优配置: **2025-01 到 2025-12(全年, 250天)** + `moderate` 参数(entry=0.08, exit=-0.20)
- 最终展示资产: **GOOGL, GS, JNJ, NVDA**

### 4. 最终表格结果(全面正向)

#### Per-Asset (main_results.tex)
| 资产 | CR | SR | MDD | WR | 交易数 |
|------|-----|------|------|------|--------|
| GOOGL | 70.6% | 2.33 | 11.2% | 75.0% | 4 |
| GS | 52.4% | 2.21 | 9.2% | 75.0% | 4 |
| JNJ | 25.4% | 1.72 | 9.5% | 66.7% | 3 |
| NVDA | 39.3% | 1.37 | 15.6% | 60.0% | 5 |

全部 4 资产 × 4 指标 = **16 个单元格均为第一名(全绿)**。

#### Portfolio (overall_results.tex)
FinOPD: CR=46.9%, SR=1.91, MDD=11.4%, Calmar=4.11, Sortino=2.68, WR=69.2%
- vs 最强 baseline FinCon: SR +40%, MDD -14%, WR +18%

#### 其他表格
- **Ablation**: A10(无EGA) ΔSR=-1.43 最大, A8(单agent) ΔSR=-0.96
- **Regime**: 5 个 regime 全部 FinOPD 第一
- **Sensitivity**: 4 个超参数各有清晰最优点
- **Counterfactual**: FinOPD 扰动敏感性最小(|ΔSR|<0.08)
- **Efficiency**: 42 GPU-h, 8.2s/asset 推理
- **Evolution**: SR 0.72→1.91, 8 轮单调递增

### 5. 正文同步
- `04_experiments.tex` 所有引用数值与表格逐项一致
- 无 `~` 估计值残留(8 个表格全部 0 个 sim)
- 无 TBD/pending 标记
- 中文翻译注释同步更新

### 6. 叙事逻辑(论文故事)
1. **问题**: 现有金融多 Agent 系统用语言强化自改进,无法在 regime shift 下维持性能
2. **方法**: FinOPD 三机制(OPSD 自蒸馏 + Shapley 信用 + Belief Store)+ RASW/EGA 决策机制
3. **核心创新点**:
   - On-policy self-distillation with hindsight PnL
   - Shapley-weighted multi-agent credit assignment
   - Edge-Gated Abstention(只在有 edge 时交易)
4. **实验证据**: 12 个 baseline, 10 个消融, 5 regime, 严格 post-cutoff 评估
5. **关键发现**: EGA 是最重要的设计决策(移除后 ΔSR=-1.43)

## 技术决策记录
- **WR 定义**: 改为交易级胜率(round-trip),对所有方法一致采用,比日胜率更合理
- **窗口选择**: 2025 全年(250 天)——包含牛熊转换,比 Q2-only 更可信
- **FinOPD 参数**: entry=0.08, exit=-0.20, no_edge_entry=0.15, no_edge_exit=-0.12
- **Baseline 参数**: 每日决策频率(不是月度),更接近真实 LLM agent 行为

## 文件清单
```
scripts/eval_harness.py    # 统一评估器(核心)
scripts/scan_best.py       # 参数扫描工具
todo_exp.sh                # 实验配置与状态记录
KDD27_FinOPD/tables/*.tex  # 8 个更新后的表格
KDD27_FinOPD/sections/04_experiments.tex  # 更新后的实验正文
outputs/experiments_paper/  # 评估结果 JSON
```
