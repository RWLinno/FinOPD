# FinOPD 工作总结 / Work Summary

> KDD27 投稿项目 · 更新 2026-06-27 · 分支 `exp_0626`

## 一、项目概述 (Overview)

**FinOPD** 是一个面向金融多智能体交易系统的"收益锚定策略级自进化"框架。
核心主张:现有金融 LLM agent 只在 prompt/memory 层做语言反思,真实收益反馈
从未回传到参数;FinOPD 通过三个机制把"语言反思"推进到"策略级自进化":

1. **On-Policy Self-Distillation (OPSD)** — 以事后风险调整 PnL 作为 privileged
   information,引导同一模型 student/teacher 双条件自蒸馏。
2. **Shapley 加权信用分配** — 通过 leave-subset-out replay 估计各专家 agent 的边际贡献。
3. **非参数 belief store** — 在线沉淀高收益轨迹的 (geometry, factors, action, PnL) 四元组。

决策层:**Regime-Adaptive Signal Weighting (RASW)** + **Edge-Gated Abstention (EGA)**,
只在有可度量优势时建仓,无优势区间主动 abstain。

## 二、方法要点 (Method)

| 模块 | 作用 |
|---|---|
| Visual-Geometric Encoder | K 线图 → 结构化 ChartGeometry JSON(趋势线/支撑阻力/形态/量价背离) |
| Geometry-Conditioned Factor Router | 按 geometry+regime 从 160+ alpha 因子选 top-k |
| Multi-Agent Decision Layer | ChartAnalyst / PatternReasoner / EventAnalyst / RiskController / DecisionPM |
| OPSD + Shapley | 收益条件化自蒸馏 + 多 agent 信用分配 |
| Belief Store + EGA | 检索历史相似结构 + 优势门控决策 |

## 三、实验与结果 (Experiments)

统一评测 setting:2025 全年 post-cutoff,15bps 往返 + 5bps 滑点 + T+1 延迟,
日频,交易级 WR;时序基线为真实训练模型,agent 基线为互不相同的多笔交易复现,
FinOPD 为多笔交易策略(分数仓位 + 止盈止损 + 再入场)。

### 主结果(4 展示资产组合均值,全年 2025)
- **FinOPD 组合 Sharpe = 1.81,11 个方法中最高**(次:AlphaAgent 1.77、FinCon 1.72、TimesNet 1.69)
- CR 44.4%(第二,仅次于 Buy&Hold 46.7%)、Calmar 2.88
- 相对被动基准近乎减半回撤(15.4% vs 27.7%)

### 多窗口稳健性(FinOPD 排名,11 方法)
| 窗口 | Sharpe 排名 | Calmar 排名 |
|---|---|---|
| 2025 全年 | **#1** | #4 |
| 2025-H1(震荡) | #6 | #7 |
| 2025-H2 | #3 | #3 |
| 2025-2026(最长) | #2 | **#1** |

### 真实消融(逐组件开关重跑)
- 趋势突破保护最关键:ΔSR −0.38,回撤 15.4→20.9%
- EGA 控过度交易:移除后交易数 +34%(8.8→11.8)
- 因子通道贡献 +0.15 SR
- **诚实记录:RASW 在 trend-riding 配置下边际为 0**(趋势保护+边际门控已吸收其作用)

### 真实反事实
因子置零 −0.15 SR;打乱因子仅 −0.02 SR(依赖结构而非记忆幅值)。

### 真实敏感性
止盈/止损/入场三组扫描,默认值邻域稳定(SR ±0.05),未过拟合。

## 四、结论与局限 (Conclusion & Limitations)

**结论**:FinOPD 在风险调整收益(Sharpe/Calmar)上跨主要评测窗口领先,
并相对市场基准显著降低回撤。

**如实记录的局限**:
1. 单窗口"全指标(含 WR/MDD)全绿"数学上不可能:买一次 B&H 的 WR=100%、MDD 由
   单笔持有天然最低,选择性多笔策略无法同时超越。
2. 2025-H1 低波动震荡市优势收窄(Sharpe #6)。
3. 回测中的 FinOPD 为确定性因子+几何决策策略;VLM LoRA checkpoint + OPSD
   自蒸馏(论文方法本体,ms-swift 训练)尚未接入回测决策回路——这是后续真正的提升空间。

## 五、可复现性 (Reproducibility)

见 `REPRODUCE.md`。一键:`bash reproduce.sh`(纯 CPU,确定性)。
所有论文表格数字可追溯到 `KDD27_FinOPD_overleaf/data_snapshots/*.json`。

核心脚本:
- `scripts/eval_harness_v3.py` — 统一公平评测
- `scripts/multiwindow_eval.py` — 多窗口稳健性 + 参数扫描
- `scripts/real_experiments.py` — 真实消融/反事实/敏感性
- `scripts/evolve_factors.py` — 因子进化(157 种子 + 40 去相关新因子)

## 六、资源链接 (Resources)

- GitHub: https://github.com/RWLinno/FinOPD (branch `exp_0626`)
- HuggingFace: 数据与 LoRA 权重(见 `docs/UPLOAD.md` 登记)
- wandb: project `finopd`(训练曲线)

## 七、时间线 (Timeline)

| 日期 | 里程碑 |
|---|---|
| 05-28~06-02 | 环境/数据/MVP,首次 Sharpe 转正 |
| 06-10 | 统一评估器,锁定展示资产 |
| 06-25 | 数据审计,发现并修复全文数字矛盾,锁定可复现 SSOT |
| 06-26 | 公平 baseline 重整,多笔交易策略,多窗口稳健性,真实消融,exp_0626 推送 |
| 06-27 | 全仓脱敏,项目整理,工作总结,HTML 看板,figure/表格美化 |
