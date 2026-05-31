# FinOPD 项目工作总结

## 一、项目定位与命名决策

### 从 FinVL-MAS 到 FinOPD

项目最初以 **FinVL-MAS**（Vision-Grounded Multi-Agent System）为题，定位为"视觉几何 + 因子路由 + 自进化"三模块并列的系统论文。经过分析当前学术热点和 KDD Research Track 的偏好，我们做出了关键的战略调整：

- **新名称**: FinOPD（Financial On-Policy Distillation）
- **核心叙事**: 聚焦 on-policy self-distillation 作为打破金融多智能体"进化死锁"的关键范式
- **调整理由**: On-policy distillation 是 2025-2026 最热门的后训练范式之一（OPSD/CRISP/ExPO 等），以此为核心卖点更容易获得 reviewer 关注

### 贡献层次重新定义

1. **Primary**: 经验驱动的双轨自进化机制（参数侧 OPSD + 非参数侧 belief consolidation）
2. **Secondary**: 几何条件化因子路由（可被奖励优化的离散策略）
3. **Enabling**: 视觉几何编码器（为 OPSD 提供结构化语义层）

---

## 二、论文框架完成度

### 当前状态：可直接填充实验结果

| 章节 | 文件 | 状态 |
|------|------|------|
| Abstract | sections/00_abstract.tex | 完成（~250 words） |
| Introduction | sections/01_introduction.tex | 完成（三段式，~1.5 pages） |
| Related Work | sections/02_related_work.tex | 完成（5 subsections，含 Evaluation Rigor） |
| Problem Formulation | sections/02b_problem.tex | 完成（C1-C3 形式化） |
| Method | sections/03_method.tex | 完成（6 subsections + Algorithm 1 + 数学公式） |
| Experiments | sections/04_experiments.tex | 完成（H1-H4 + 表格模板 + 图引用位置） |
| Conclusion | sections/05_conclusion.tex | 完成 |
| Appendix | sections/appendix.tex | 完成（因子库/Agent角色/超参数表） |
| Bibliography | refs.bib | 完成（35+ 引用） |

### 论文亮点

- **Algorithm 1**: 完整的 FinOPD 自进化循环伪代码
- **Equation (1)**: Gumbel-Softmax top-k 因子路由公式
- **Equation (2)**: 广义 JSD 分布匹配目标
- **Equation (3)**: Per-token KL clipping 公式
- **Equation (4)**: Belief store capacity 约束
- **Table 1**: 消融配置表（A1-A10）
- **Table 2-3**: 主实验结果模板（待填充）
- **Figure placeholders**: Evolution curve, counterfactual delta

---

## 三、实验计划概览

### 实验看板 (todo_exp.sh)

共 17 个后台任务，覆盖 6 个 Stage：

| Stage | 任务数 | 关键脚本 | 预计耗时 |
|-------|--------|----------|----------|
| 1. Data | 2 | run_data_pipeline, run_chart_geometry_build | 1-2 天 |
| 2. VLM | 2 | run_vlm_lora_train, run_vlm_lora_eval | 2-3 天 |
| 3. Router+MVP | 2 | run_factor_router_train, run_mvp | 2-3 天 |
| 4. Self-Evolution | 4 | run_opsd_stability/full, run_belief, run_evolution_curve | 5-6 天 |
| 5. Main Exp | 5 | run_main/ablations/baselines/counterfactual/regime | 3-4 天 |
| 6. Report | 2 | run_live_forward, generate_report | 持续 |

### 关键依赖关系

```
Stage 1 → Stage 2 → Stage 3 (MVP 检查点)
                         ↓
                    Stage 4 → Stage 5 → Stage 6
```

### Acceptance Criteria

- H1: A2 vs A1 在 volatile regime 上 Sharpe 下降 ≥0.2
- H2: A1 vs A4 tool-call 准确率提升 ≥10pp
- H3: A1 vs A5 alpha decay 下降 ≥30%；A1 vs A6b Sharpe 下降 ≥0.15
- H4: Evolution curve 3 seed 单调改进
- Live-forward 至少跑满 1 个月

---

## 四、文献调研覆盖

### 已引用文献分布（35+ 篇）

- 金融多智能体系统: TradingAgents, FinCon, FinAgent, R&D-Agent, AlphaAgent, FinTeam, MAS4TS, FinRobot, FinMem
- 自进化 Agent: SE-Agent, SEEA-R1, Self-Challenging, Agent0, R-Zero, Reflexion
- On-Policy Distillation: OPSD, CRISP, ExPO, GKD, DPO, GRPO, Alignment Tipping
- 金融图表理解: FinChart-Bench, ChartMuseum, Time-VLM, VisionTS, Qwen2.5-VL
- 评估严谨性: DeepFund, Look-Ahead-Bench, FactFin, DSOF, FinMCP-Bench, TradeTrap
- 时序基线: PatchTST, TimesNet, iTransformer
- 工具使用: ReAct
- 量化金融: The Losing Winner

---

## 五、当前进度与下一步

### 已完成

1. 项目命名与叙事重构（FinVL-MAS → FinOPD）
2. 完整实验计划 prompt（docs/experiment_plan_prompt.md）
3. KDD 论文 draft 全部章节（abstract 到 appendix）
4. 数学公式与算法伪代码
5. 实验结果表格模板（待填充数据）
6. Figure prompts（8 张核心图的生成规格）
7. refs.bib（35+ 引用）
8. todo_exp.sh 实验看板
9. 各 run_*.sh 实验脚本

### 下一步（实验窗口执行）

1. **立即启动**: Stage 1 数据构建（run_data_pipeline + run_chart_geometry_build）
2. **Week 1 末**: Stage 2 VLM LoRA 训练
3. **Week 2 末**: Stage 3 MVP 检查点判定
4. **Week 3-4**: Stage 4 OPSD 自进化（先 AAPL 稳定性验证）
5. **Week 5**: Stage 5 全量实验 + 消融
6. **Week 6**: 填充实验数据到论文 + 画图 + arXiv 预印

### 风险与 Fallback

- **Plan A**: Full FinOPD（OPSD + Belief + VGE + Router）
- **Plan B**: 若 OPSD KL 爆炸 → 仅 Belief + GRPO-lite Router
- **Plan C (MVP)**: 若自进化全部受阻 → VGE + Router 系统论文，改回 FinVL-MAS

---

## 六、文件清单

```
FinVL-MAS/
├── todo_exp.sh                          # 实验总看板
├── docs/
│   ├── experiment_plan_prompt.md        # 实验 Agent 完整指令
│   ├── exp-info.md                      # 环境凭证
│   ├── best_factor.json                 # 160 个自进化因子
│   ├── code-rule.md                     # 编码规范
│   └── ai-writing.md                    # 写作 prompt 集合
├── papers/
│   ├── main_finvl.tex                   # 主文件（FinOPD 版本）
│   ├── refs.bib                         # 参考文献（35+ 篇）
│   ├── sections/
│   │   ├── 00_abstract.tex
│   │   ├── 01_introduction.tex
│   │   ├── 02_related_work.tex          # 5 subsections
│   │   ├── 02b_problem.tex              # Problem Formulation
│   │   ├── 03_method.tex                # 含 Algorithm 1 + 4 equations
│   │   ├── 04_experiments.tex           # 含 3 table templates
│   │   ├── 05_conclusion.tex
│   │   └── appendix.tex
│   └── figure_prompts/
│       └── figure_specs.md              # 8 张图的生成规格
├── experiments/
│   ├── run_data_pipeline.sh
│   ├── run_chart_geometry_build.sh
│   ├── run_vlm_lora_train.sh
│   ├── run_vlm_lora_eval.sh
│   ├── run_factor_router_train.sh
│   ├── run_mvp.sh
│   ├── run_opsd_stability.sh
│   ├── run_opsd_full.sh
│   ├── run_belief_consolidation.sh
│   ├── run_evolution_curve.sh
│   ├── run_main.sh
│   ├── run_ablations.sh
│   ├── run_baselines.sh
│   ├── run_counterfactual.sh
│   ├── run_regime_analysis.sh
│   ├── run_live_forward.sh
│   └── generate_report.sh
└── configs/
    ├── default.yaml
    └── synth.yaml
```
