# FinOPD: KDD 2027 Conference Review

## 1. Report Metadata

- Review date: 2026-07-27
- Target venue/year/track: KDD 2027 Research Track（按 fresh submission 审查）
- Paper title: *FinOPD: On-Policy Distillation for Self-Evolving Financial Multi-Agent Systems*
- Input materials reviewed: 12-page PDF；正文 pp. 1-8，参考文献 pp. 9-10，附录 pp. 10-12
- Search basis: KDD 2027 官方 CFP；公开网页安全检索；arXiv 相关工作；Qwen 官方发布页与模型卡
- Report file: `2026-07-27-finopd-kdd-2027-conference-review.md`
- Reviewer mode: standard / full scientific + writing + format review
- Privacy boundary: 未使用论文私有原句作为搜索查询；仅使用公开方法族、任务词和公开模型名

## 2. Desk Rejection Assessment

- **Paper length — pass.** 正文恰为 8 页，之后为参考文献和无页数上限的 Appendix，符合 KDD 2027 Research Track 的“8 content pages + references + optional Appendix”要求。
- **Topic compatibility — pass.** 金融时序决策、LLM agent、continual/self-evolving learning 和可复现实证均属于 KDD Research Track 可接受范围。
- **Minimum quality — pass.** 摘要、相关工作、问题定义、方法、实验、局限和附录齐全，PDF 可读。
- **Policy/anonymity/compliance — fail（可直接导致 desk reject）.** PDF p. 1 明示 7 位作者、单位、邮箱，并使用带作者信息的页眉及 camera-ready 版权/DOI 占位符。KDD 2027 官方要求 double-blind，并推荐 `\documentclass[sigconf,anonymous,review]{acmart}`；CFP 明示格式违规将 desk-reject。
- **Prompt injection and hidden manipulation detection — pass.** 对全部 12 页提取文本及 PDF 元数据检查，未发现针对 reviewer/LLM 的隐藏指令；PDF 无 JavaScript、表单或加密。
- **Ethics and reviewability — uncertain.** 有 Limitations、Ethical Considerations 和 Generative AI Usage，但 50k weakly labeled charts、1k human-verified samples、新闻/行情数据的来源、许可、标注流程及隐私/版权边界未交代。

**Desk rejection risk: likely（若此 PDF 即投稿版本）**

**Reason:** 明显违反 double-blind anonymity；科学问题尚未进入实质评审就可能被退稿。

**Can be fixed before review?** yes；匿名化是立即可修复项，但不解决下述科学硬伤。

## 3. Paper Summary And Contribution Map

本文研究金融多智能体系统如何从延迟到达的真实组合结果中更新决策策略。FinOPD 在训练前生成并冻结 157 个可执行 alpha factors；训练中由当前 student 产生 point-in-time 轨迹，待 20 日 horizon 结束后，frozen teacher 接收收益、回撤、CVaR 和换手率构成的 hindsight summary，再以 agent-weighted token-level JSD、clipped teacher-student KL 和 round-start reference KL 更新 student；同时更新因子 router，并将高效用成熟 episode 写入 time-safe memory；部署时通过 regime-aware selective execution 决定买、卖或 abstain。

- **Claimed problem:** 现有金融 agent 能组织证据、工具和记忆，但没有把自身已成熟的 portfolio outcome 直接转成当前策略的 dense supervision。
- **Claimed gap:** 延迟反馈、on-policy endogenous trajectory、多 agent 共享 credit，以及 policy/factor/memory 的异步更新时间尚未在一个 temporal-safe 框架中统一。
- **Method/contribution map:** frozen factor mining -> Gumbel top-k router -> five-agent chain -> post-horizon teacher -> Shapley-like agent credit -> OPD update -> time-safe episodic memory -> regime-aware execution。
- **Evidence package:** 四只美国大盘股；2025-01 至 2026-05 单一测试窗口；12 个基线；逐资产 CR/SR/Calmar；三个时间切片；learning/validation diagnostic ablation；灵敏度和决策 trace。
- **Stated limitations:** 单次训练、四只股票、一个 17 个月窗口、无置信区间、未因果分离 OPD 与 memory、hindsight utility 可能错设、未覆盖市场冲击和结构突变。

## 4. Search And Related-Work Basis

- **Queries used:** `"on-policy distillation" financial trading agent`；`"self-evolving" financial trading agent`；`hindsight financial trading LLM agent distillation`；`"on-policy" distillation multi-agent hindsight`；KDD 2027 official research-track rules；Qwen3.5 official release/model card。
- **Sources searched:** KDD 2027 官方 CFP；arXiv；Alibaba/Qwen 官方发布页；Hugging Face 官方 Qwen 模型卡；论文参考文献。
- **Closest works found:** GKD（论文已引）；SEED（已引，arXiv:2607.14777）；MAD-OPD（未引，arXiv:2605.01347）；SERL/Selective Hindsight Distillation（未引，arXiv:2605.19447）。
- **Unverified related-work risks:** 搜索不是系统综述；未发现与“financial trading + OPD”完全同构的公开论文，但不能据此证明 first-ever。
- **Source-quality screening status:** venue 规则取自官方 CFP；模型发布时间取自 Alibaba 官方页；算法近邻取自 arXiv 原始条目；未以博客或聚合站作为关键证据。
- **Verification links:** [KDD 2027 Research Track CFP](https://kdd2027.kdd.org/research-track-call-for-papers/)；[Qwen3.5 official release](https://www.alibabagroup.com/document-1960233590314762240)；[Qwen3.5-9B model card](https://huggingface.co/Qwen/Qwen3.5-9B)；[SEED](https://arxiv.org/abs/2607.14777)；[MAD-OPD](https://arxiv.org/abs/2605.01347)；[SERL](https://arxiv.org/abs/2605.19447)。

## 5. Expected Review Outcome

- **Expected outcome:** 当前文件 likely desk reject；忽略匿名问题后，科学评审为 **Reject（3/10）**。
- **Main accept signal:** 问题重要，temporal staging 清楚，作者主动区分部署信息与 post-horizon supervision，并诚实写出单次窄窗口和缺少置信区间等限制。
- **Main reject signal:** “strict post-cutoff”缺乏成立条件，主表把逐资产 Sharpe/Calmar 的算术平均写成 portfolio/aggregate 指标，且核心结果只有四只股票、单一路径、单次训练、无统计不确定性与 held-out 机制消融。
- **Confidence:** 4/5；全文、附录、官方 KDD 规则和有限公开近邻检索均已读，但没有代码、原始日收益、数据快照和训练日志，无法复算交易结果。

## 6. Strengths And Weaknesses

### Strengths

- **问题与时序边界明确。** pp. 2-6 把 rollout、horizon closure、teacher annotation、policy/router update 和 memory admission 分开，避免最直接的 future chart/OHLCV 注入部署输入。
- **方法组件可追踪。** Eqs. (6)-(10) 区分 teacher、student 和 round-start reference；Algorithm 1 明示 accept-or-revert chronology。
- **结果没有完全掩盖失败边界。** p. 6 主动指出 JPM return 不如 Buy & Hold，p. 8 承认 long-oriented policy、非单调灵敏度和无法分离 OPD/memory。
- **局限披露优于常见金融 agent 稿件。** pp. 8、11-12 明确承认单一训练 run、单一市场周期、无 CI 和 point-in-time data 依赖。
- **排版整体专业。** 公式、算法、表格和 Appendix 结构完整；正文 8 页限制处理得较紧凑。

### Major / Fatal Weaknesses

#### W1. “Strict post-cutoff”可能被 foundation-model 权重直接破坏

- **Evidence basis:** 测试期为 2025-01 至 2026-05（p. 5-6），决策 backbone 为 Qwen3.5-9B（pp. 4、6）。Alibaba 官方页显示 Qwen3.5 系列在 2026-02 发布；官方模型卡未给出足以证明早于 2025-01 的训练数据 cutoff。该 checkpoint 在测试期开始时并不存在。
- **Reviewer deduction:** 这是 retrospective backtest，不是严格 post-cutoff/live evaluation。即使每个 prompt 只含 point-in-time input，模型权重仍可能编码 2025 年公司事件、新闻与价格叙事。所有 LLM baseline 共用同一 backbone 只能改善相对公平性，不能恢复绝对 temporal validity。
- **Required fix:** 换用训练 cutoff 明确早于 2025-01 的 frozen backbone；或把测试期后移到模型和所有辅助数据 cutoff 之后；同时做 event/news memorization audit、无文本/无 ticker-name 对照和 model-weight contamination 声明。

#### W2. Table 1 不是所声称的 portfolio/aggregate evaluation

- **Evidence basis:** Table 2 的 FinOPD 四资产 CR 为 133.7、52.8、41.1、15.8，算术平均正好为 60.85 -> Table 1 的 60.9；SR 平均为 1.405 -> 1.41；Calmar 平均为 3.2975 -> 3.30。Buy & Hold 亦完全相同。Appendix B.2 还明确称 Table 1 是 asset-averaged CR and Calmar。
- **Reviewer deduction:** 平均单资产 Sharpe/Calmar 不是组合 Sharpe/Calmar，不能被称作“portfolio results”“aggregate Sharpe/Calmar”。CR 只有在明确资本分配、现金与再平衡规则下才可能等于某种组合回报；SR 和 Calmar 必须从同步组合日收益和组合 drawdown 重算。摘要、Fig. 1、Table 1 caption 和结论的核心领先主张因此被误标。
- **Required fix:** 发布逐日 synchronized portfolio PnL；说明 initial capital、跨资产权重、现金、再平衡和风险预算；从 portfolio return series 重算 CR/SR/MDD/Calmar，并把所有“aggregate/portfolio”表述与结果同步更新。

#### W3. 证据不足以支持“13 方法中第一”和跨市场鲁棒性

- **Evidence basis:** 只有 4 个高度相关的美国 mega-cap、约 350 个交易日、一个 bullish/AI-heavy 时段、一个 selected checkpoint、一次训练；p. 6 明示不估计 optimization variance 或 market-history uncertainty。
- **Reviewer deduction:** 12 个方法 x 多指标 x 多资产的比较存在 data-snooping/multiple-comparison 风险；没有 block bootstrap、Deflated Sharpe、White Reality Check/SPA、置信区间或跨 seed 结果。“top-4 across three slices”也不是独立重复，因为切片来自同一条路径。
- **Required fix:** 多个不重叠市场周期、更多股票和行业、熊市/横盘期、至少 3-5 个训练 seeds；对 synchronized portfolio daily returns 做 block bootstrap 与多重比较校正；报告效应量和 CI，而不只报告排名。

#### W4. 核心机制没有在 held-out test 上被因果隔离

- **Evidence basis:** p. 7 明示 Fig. 4/Table 6 使用 learning-phase diagnostic window，不能与 held-out SR 1.41 比较；p. 8 承认 trace 不因果分离 OPD 与 memory。Table 4 的 `w/o OPD`、`w/o Belief`也只给 diagnostic SR。
- **Reviewer deduction:** 论文题目和方法核心是 OPD/self-evolution，但主测试没有 full factorial `OPD x memory x router/factors x execution guard`；当前显著收益反而主要来自 trend-break 和 turnover guard。无法判断领先来自新 OPD、记忆、传统风险控制，还是 validation tuning。
- **Required fix:** 在锁定的 held-out windows 上报告 full、w/o OPD、vanilla GKD/KD、w/o memory、w/o both、w/o credit、w/o reference KL、fixed router、w/o execution guard；保持相同 seed、预算、数据与选择协议。

#### W5. 若干中心量和训练步骤未定义到可实现程度

- **Evidence basis:** scalar utility `U`/`J` 无公式和权重；hindsight summary 的 prompt、归一化和 teacher action contract 仅为 abridged version；`D_eta` 架构与训练不明；Eq. (5) 的 Gumbel top-k subset probability `P_psi(I_t|...)`未定义或给出可计算估计；RASW regime weights、confidence calibration、trend-break、adaptive turnover、position sizing、Table 9 的 `stability`均缺精确定义。
- **Reviewer deduction:** 这些量同时控制 router reward、memory admission、Shapley credit、teacher supervision 和最终执行，是方法核心而非实现细节。读者无法复现，也无法排除 utility/guard engineering 是主要收益来源。
- **Required fix:** 给出 utility 的完整方程、所有尺度/权重；完整 prompt schema；`D_eta` 和 calibration 训练；top-k log-probability estimator；所有 execution rules；附可运行伪代码和配置文件。

#### W6. 数据、baseline 和 selection protocol 不足以审计

- **Evidence basis:** 50k weak labels、1k verified charts 没有来源日期、ticker split、annotator agreement、license 或 held-out encoder accuracy；新闻/filing timestamp 数据源未写；157 factors 的候选总数和 multiple-testing control 未写；12 个 baseline 的版本、prompt、tuning budget 和适配方式未写；PatchTST/iTransformer 只出现在 Appendix diagnostic efficiency 表，未进入主 held-out comparison。
- **Reviewer deduction:** 不能确认视觉数据与 test 是否重叠、新闻是否 point-in-time、因子是否 selection-overfit，也不能确认 baseline 是否被等预算调优。R&D-Agent(Q)/AlphaAgent 原本偏 alpha mining，如何转成同一 daily allocation policy 尤其关键。
- **Required fix:** 数据卡、timestamp policy、corporate-action/交易成本规则、候选因子漏斗、baseline implementation matrix、统一 tuning budget；把强时序模型及 vanilla OPD/GKD/SEED-style 对照加入 held-out test。

### Writing And Presentation Concerns

| ID | Current role | Reviewer takeaway | Main problem | Concrete edit | Severity |
| --- | --- | --- | --- | --- | --- |
| Abstract-P1 | 方法与主结果 | FinOPD 严格 post-cutoff 且组合指标第一 | “strict/post-cutoff/aggregate”均超出当前证据 | 在修复 W1/W2 前改为 retrospective point-in-time backtest，并写 asset-averaged metrics | high |
| Intro-Fig1 | 动机与方法总览 | 现有 GPT-4o/Claude/Gemini live returns 失败 | 图中 backtest-vs-live bars 没有来源，容易被当作实证数据 | 若为 conceptual，明确标注 schematic 并移除模型名/数值视觉；若为数据，补来源和协议 | high |
| Method-4.3 | Router 定义 | top-k router 可由 centered utility 更新 | `log P_psi(I_t \| ...)`不可直接复算 | 给出 Plackett-Luce/Gumbel-top-k 概率或使用的 gradient estimator | high |
| Method-4.4 | Hindsight supervision | teacher 产生更优 dense target | 只有执行动作的 outcome，没有反事实最优动作；“teacher ceiling”并非严格上界 | 解释 teacher target 的决策含义；将 ceiling 政名为 privileged diagnostic policy | high |
| Exp-5.1 | Protocol | 所有方法完全公平可比 | baseline 版本、prompt、调参预算和股票到组合的映射缺失 | 主文增加 compact protocol matrix，详细配置放 Appendix | high |
| Exp-5.2 | Main result | FinOPD portfolio CR/SR/Calmar 第一 | 实际是逐资产指标均值 | 改为真正 portfolio series 或准确命名为 macro-average of per-asset metrics | high |
| Exp-5.4/5.5 | Mechanism | 保护、换手、OPD、memory 解释性能 | 1.81、1.92、1.28 三个 diagnostic/validation SR 的窗口关系不清 | 增加 split/time-line 表，逐表写日期、选择用途、是否可用于 claim | medium |
| Appendix-T3/T4 | 复现与消融 | 提供了全部实现细节 | `Belief`、`memory`、`J/U`、`stability`、`adversarial refresh`术语漂移或未定义 | 建立统一 glossary；删除未使用参数或在算法中落位 | medium |
| Figs. 1-3 | 总览 | 系统很完整 | 信息密度过高，最小字体接近不可读，证据图与概念图混合 | 拆成 chronology 图与 learning-objective 图；放大关键变量 | medium |

### Format/Venue Concerns

- 必须删除作者、单位、邮箱、`Ruan et al.` 页眉和可识别链接，切换 anonymous review mode。
- p. 1 的 copyright/ISBN/DOI `XXXXXXX` 是 camera-ready 占位，不应出现在 review submission。
- 正文页数合规；但 KDD 明示前 8 页需 self-contained，核心 utility、baseline protocol 和数据边界不应只依赖 Appendix。
- PDF 仅被视觉检查，未取得 TeX source，因此无法检查 undefined refs、duplicate labels、overfull box 或 package-level format override。

## 7. Potentially Missing Related Work

### MAD-OPD: Breaking the Ceiling in On-Policy Distillation via Multi-Agent Debate

- **Status:** searched；arXiv:2605.01347，2026-05-02
- **Why relevant:** 同样针对 agentic OPD，提出 multi-agent teacher/debate、token-level supervision，并明确主张 JSD 对 agentic stability 的作用。
- **Overlap:** agentic on-policy state、multi-agent contribution weighting、JSD token distillation。
- **Needed comparison:** 解释 FinOPD 的“多 agent credit over one trading system”与 MAD-OPD 的“multi-teacher debate”差异；至少加入 related-work technical comparison，最好加入相同 finance protocol 下的 OPD baseline。

### What and When to Distill: Selective Hindsight Distillation for Multi-Turn Agents (SERL)

- **Status:** searched；arXiv:2605.19447，2026-05-19
- **Why relevant:** 研究 hindsight/environment feedback 应在何处、以何强度进入多轮 agent training，正对应 FinOPD 从 horizon outcome 到 token supervision 的核心问题。
- **Overlap:** delayed task outcome、step/token credit、selective weighting、hindsight distillation。
- **Needed comparison:** 说明 FinOPD agent-level Shapley weighting 是否解决 SERL 的 feedback placement/magnitude 问题；增加 step/token selection 对照。

### SEED: Self-Evolving On-Policy Distillation for Agentic Reinforcement Learning

- **Status:** user-provided/cited；arXiv:2607.14777
- **Why relevant:** 把 completed on-policy trajectories 变成 hindsight skills，并把概率变化蒸馏回 policy，是最接近的通用框架。
- **Overlap:** self-evolution、matured trajectory、hindsight、token-level on-policy distillation。
- **Needed comparison:** 现有 related work 只有概述；应逐轴比较 teacher source、hindsight representation、outcome objective、credit granularity、RL coupling、memory 和 leakage boundary，并加入可执行 baseline。

## 8. Claim-Evidence Audit

| Claim | Where stated | Evidence provided | Strength | Reviewer deduction | Required fix |
| --- | --- | --- | --- | --- | --- |
| 严格 post-cutoff，部署不见未来 | Abstract；Fig. 1；pp. 2、5-6 | point-in-time prompts、horizon 后 teacher、one-day delay | weak | Qwen3.5 于测试期内发布且 cutoff 未证；权重污染未排除 | 使用 cutoff 早于测试的模型并做 contamination audit |
| 从真实 portfolio utility 直接学习 | Abstract；pp. 2-5 | hindsight vector、`U`、agent credit、OPD loss | weak | `U`未定义；只有执行动作 outcome；teacher target validity 未验证 | 公开 utility/prompt，加入 counterfactual/alternative target 与 calibration |
| agent credit 改善共享终局 credit | Contribution；Eq. (7) | 8 permutation Shapley-like weights | weak | 无 credit quality/variance/sensitivity；无 uniform/no-credit held-out 对照 | 对 B、temperature、uniform credit 做 held-out ablation 与误差分析 |
| factor library 可审计且有效 | pp. 4、7、10 | 157 factors，IR distribution，fixed manifest | weak | 候选数/selection bias 不明；zero factors 仅降低 0.03 diagnostic SR | 公开 factor funnel 和 holdout IR；弱化其性能贡献主张 |
| time-safe memory 带来 self-evolution | pp. 5、7、11 | hit rate 12.3%->62.4%；w/o Belief diagnostic SR | weak | hit rate 与性能共同上升不是因果；未在 held-out test 隔离 | factorial held-out ablation 和 retrieval-quality/error analysis |
| FinOPD 在 13 方法中 aggregate/portfolio 第一 | Abstract；Table 1；Conclusion | 四资产指标均值；Table 2 | invalid as stated | 平均 per-asset SR/Calmar 被误称 portfolio；无 uncertainty | 从 synchronized PnL 重算并做统计检验 |
| 跨时间和 regime 鲁棒 | Sec. 5.3；Table 5 | 同一测试路径的 3 个切片和 regime partition | weak | 非独立样本；normal/calm zero exposure 的 Sharpe 应为 undefined 而非 0.00 | 多周期 walk-forward；把零方差 Sharpe 标为 N/A |
| OPD 与 memory 构成主要创新来源 | Title；Secs. 5.4-5.5 | learning-phase diagnostics | weak | 最主要局部下降来自 trend-break/turnover；无 held-out factorial isolation | 在主测试中加入 OPD/memory/guard 全因子消融 |

## 9. Experiment / Benchmark / Reproducibility Audit

- **Baselines — major concern.** 基线类型多，但缺版本、prompt、代码来源、调参预算、随机种子和从 alpha miner 到 allocation policy 的适配细节；PatchTST/iTransformer 未进入主 held-out 表；缺 vanilla GKD/KD、DPO/GRPO、SEED-style 和 uniform-credit OPD。
- **Ablations — major concern.** 最关键的 OPD、memory、credit、reference KL、router 仅在 learning/validation diagnostic 中零散出现；主 held-out test 没有 factorial ablation。
- **Datasets/benchmarks — major concern.** 四只 mega-cap 太窄且高度相关；视觉训练集、事件数据、行情 vendor、timestamp、corporate actions、dividend、borrow/short constraints 不明。
- **Metrics — fatal concern for main claim.** Table 1 是 per-asset metric macro-average，不是 portfolio metric；zero-exposure Sharpe 被写成 0；risk-free rate、annualization、daily return construction 未给出。
- **Statistical rigor — major concern.** 单一 checkpoint、无 seeds、无 block bootstrap/CI、无 multiple-testing correction；作者已承认结果仅为 descriptive evidence。
- **Robustness/failure cases — partial.** 有 temporal slices、regime partition、threshold/top-k sensitivity 和一个 decision trace；但均来自同一路径或 validation，不能替代独立市场周期。
- **Implementation details — insufficient.** utility、router subset probability、allocation head、calibration、regime detector、execution guards 和 data pipeline 未完整定义。
- **Artifacts and reproducibility — insufficient.** 未提供 anonymized repository、daily PnL、factor manifest、prompts、config、seeds 或 baseline scripts。
- **Limitations — good disclosure, weak remediation.** 局限写得诚实，但其中“无 statistical reliability”“未 causal separate OPD/memory”直接削弱中心结论，不能仅靠 disclosure 消解。

## 10. Multi-Reviewer Panel

### Reviewer A — Best-Justified Accept Case

- **Expertise:** LLM agents / applied finance
- **Likely score:** 6/10 borderline positive
- **Confidence:** 3/5
- **Main positive signal:** 将 delayed outcome、on-policy prefix、agent credit、policy drift guard 和 mature memory 放入同一 chronology，问题设置有现实意义。
- **Main negative signal:** 证据范围窄，且真实 portfolio 指标没有计算。
- **Evidence basis:** pp. 2-6 method chronology；Table 2；Limitations。
- **Score-change condition:** 若重算真实组合并在多个周期保持显著优势，可升到 7；若泄漏成立，降到 2。

### Reviewer B — Critical Reviewer

- **Expertise:** empirical ML / financial backtesting
- **Likely score:** 2/10 strong reject
- **Confidence:** 5/5
- **Main positive signal:** 论文主动承认 deterministic single-run evidence 的限制。
- **Main negative signal:** Qwen3.5 时间污染与 Table 1 指标误标共同破坏中心实证结论。
- **Evidence basis:** pp. 4-6；Tables 1-2；Alibaba Qwen3.5 official release date。
- **Score-change condition:** 必须重新做 cutoff-safe backtest 和 synchronized portfolio evaluation，不能靠 rebuttal 文本修复。

### Reviewer C — Method / Soundness

- **Expertise:** knowledge distillation / policy learning
- **Likely score:** 3/10 reject
- **Confidence:** 4/5
- **Main positive signal:** generalized JSD、directional KL cap 与 reference KL 的角色区分较清楚。
- **Main negative signal:** utility、teacher target validity、router subset likelihood 和 allocation head 均未定义充分；teacher 只看执行动作的 outcome，无法自动成为 action oracle。
- **Evidence basis:** Eqs. (5)-(10)，Algorithm 1，Appendix A.1/A.3。
- **Score-change condition:** 补完整定义并加入 vanilla OPD、uniform credit、alternative hindsight target 对照后可升 1 分。

### Reviewer D — Evidence / Experiment

- **Expertise:** time-series evaluation
- **Likely score:** 2/10 strong reject
- **Confidence:** 5/5
- **Main positive signal:** 有逐资产表、时间切片、灵敏度和局部 intervention。
- **Main negative signal:** 4 assets x one path x one run，无 CI；主表不是 portfolio；核心消融不在 held-out test。
- **Evidence basis:** Tables 1-2、4-9；Sec. 5.1 声明 descriptive evidence。
- **Score-change condition:** 多周期、多 seed、block bootstrap、真实 portfolio 和 locked held-out factorial ablation 全部到位后可升到 5-6。

### Reviewer E — Novelty / Positioning

- **Expertise:** agentic OPD / self-improving agents
- **Likely score:** 4/10 weak reject
- **Confidence:** 4/5
- **Main positive signal:** 没有在有限搜索中发现完全相同的 finance-specific OPD system；temporal-safe integration 有应用新意。
- **Main negative signal:** 通用 OPD novelty 接近 GKD/SEED，并遗漏 MAD-OPD 和 SERL；当前更像多组件系统集成，算法 delta 未被对照实验隔离。
- **Evidence basis:** Related Work；公开 arXiv 近邻。
- **Score-change condition:** 加入 technical comparison 和 direct baselines，证明 marginal credit/time-safe staging 带来独立增益。

### Reviewer F — Writing / Clarity

- **Expertise:** KDD paper communication
- **Likely score:** 5/10 borderline negative
- **Confidence:** 5/5
- **Main positive signal:** 叙事主线和 temporal chronology 可恢复，结果边界写得相对克制。
- **Main negative signal:** `portfolio/aggregate/post-cutoff/ceiling`过度表述；图 1 无来源视觉；多个术语和 validation windows 不一致。
- **Evidence basis:** Abstract、Figs. 1-3、Secs. 5.2-5.6、Tables 4/6/7/9。
- **Score-change condition:** 修正 claim-evidence、统一 glossary/split timeline、简化图后 clarity 可到 4/5。

### Reviewer G — Ethics / Reproducibility

- **Expertise:** responsible financial AI
- **Likely score:** 4/10 weak reject
- **Confidence:** 4/5
- **Main positive signal:** 有投资建议免责声明、human approval/exposure limit/market-impact 风险声明和 AI 使用披露。
- **Main negative signal:** 数据许可、标注伦理、新闻/filing timestamp、artifact 和 model-weight contamination 未处理。
- **Evidence basis:** pp. 8-12。
- **Score-change condition:** 完整 data/model card、license、timestamp audit 和匿名 artifact 可提升 1 分。

### Reviewer H — Domain Application

- **Expertise:** quantitative finance / portfolio construction
- **Likely score:** 2/10 strong reject
- **Confidence:** 4/5
- **Main positive signal:** 显式考虑交易成本、slippage、delay、drawdown 和 abstention。
- **Main negative signal:** 没有真实 portfolio construction；四只多头 mega-cap 和 1.8% sell share 不足以说明通用金融 edge；borrow、dividend、corporate action、cash yield、market impact 未定义。
- **Evidence basis:** Secs. 5.1、5.6；Tables 1-2；Fig. 6。
- **Score-change condition:** 多资产组合、熊市/横盘周期、真实执行约束和 portfolio PnL 审计后再评。

### Reviewer I — Evidence / Ablation

- **Expertise:** causal mechanism diagnosis
- **Likely score:** 2/10 strong reject
- **Confidence:** 5/5
- **Main positive signal:** 作者没有把 learning-phase ablation 伪装成 test-set result，并承认不能因果分离。
- **Main negative signal:** 恰因为不能分离，题目中的 OPD/self-evolution 缺少决定性证据；最大局部增益来自传统 execution guards。
- **Evidence basis:** Secs. 5.4-5.6；Tables 4、6、8。
- **Score-change condition:** 预注册/锁定的 held-out factorial study 可显著改变判断。

### Reviewer J — Reproducibility

- **Expertise:** ML systems artifacts
- **Likely score:** 2/10 strong reject
- **Confidence:** 5/5
- **Main positive signal:** 给出部分 LoRA、KL、top-k、memory 和 compute 参数。
- **Main negative signal:** 缺数据快照、daily PnL、utility、prompts、D_eta、router estimator、baseline configs、factor manifest 和代码。
- **Evidence basis:** Appendix A-B。
- **Score-change condition:** 提供匿名 artifact 和从原始 point-in-time data 到所有表格的一键流水线后可到 4/5。

### Reviewer K — Novice Advocate

- **Expertise:** general KDD reader
- **Likely score:** 4/10 weak reject
- **Confidence:** 5/5
- **Main positive signal:** 图 2 与 Algorithm 1 帮助理解总体流程。
- **Main negative signal:** 图 1-3 过密，`U/J/Belief/RASW/EGA/stability`需要来回查找，三个不同 diagnostic SR 难以区分。
- **Evidence basis:** pp. 1、3、5、10-12。
- **Score-change condition:** 一张 split/claim map、一张简化 chronology 图和统一术语表即可明显改善。

### AC / Meta-Reviewer

- **Agreement:** 所有实证/领域/复现视角均认为当前证据不足；方法视角认可 chronology，但不认为公式和 target 已充分验证。
- **Disagreement:** 最有利视角把本文看作有价值的 finance-specific system integration；批判视角认为 temporal contamination 和 metric mislabeling 已足以否定主结论。
- **Decisive positive axis:** delayed-outcome、point-in-time、dual-track evolution 的统一问题定义。
- **Decisive negative axis:** evaluation validity，而不是语言表达。
- **Unresolved evidence:** model pretraining cutoff、原始 daily PnL、真正 portfolio metric、数据 timestamp、baseline configs、held-out ablations。
- **AC stance:** Reject；此外当前 PDF 先有 likely desk-reject anonymity violation。

## 11. Concerns Table

| ID | Severity | Concern | Evidence basis | Affected criterion | Fix class | Required action | Owner skill | Score-change condition |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C0 | fatal | 未匿名 | p. 1 作者/单位/邮箱，全部页眉 | compliance | venue-mismatch | anonymous review template，移除识别信息 | ccf-submission-checker | 消除 desk reject 风险，不直接提高科学分 |
| C1 | fatal | Qwen3.5 可能包含测试期知识 | test 2025-01 起；模型 2026-02 发布 | soundness/evidence | method/soundness | cutoff-safe 模型或后移测试，并做 contamination audit | ccf-experiment-designer | 若通过，overall +1；若确认泄漏，维持 1-2 |
| C2 | fatal | 平均 per-asset SR/Calmar 被称为 portfolio | Tables 1-2；Appendix B.2 | evidence | experiment | 从 synchronized PnL 重算 portfolio metrics | ccf-experiment-designer | 真实组合仍领先且有 CI，overall +1 |
| C3 | major | 单路径、单 run、无统计检验 | Sec. 5.1；Limitations | evidence | experiment | 多周期/seed、block bootstrap、multiple-test correction | ccf-experiment-designer | 可使 Evidence 2->4 |
| C4 | major | OPD/memory 无 held-out 因果消融 | Secs. 5.4-5.6；Tables 4/6/8 | novelty/evidence | experiment | locked factorial ablation + direct OPD baselines | ccf-experiment-designer | 独立增益成立可 overall +1 |
| C5 | major | utility、router、allocator、execution 未定义 | Eqs. (5)-(14)；Appendix | soundness/reproducibility | method/soundness | 完整公式、estimator、prompt、配置和伪代码 | ccf-paper-writer | Soundness/Reproducibility 各 +1 |
| C6 | major | 数据/label/timestamp/license 不可审计 | Sec. 4.2、5.1 | reproducibility/ethics | reproducibility | data card、date split、license、timestamp audit | ccf-paper-writer | 复现 2->3/4 |
| C7 | major | baseline 公平性与缺失强对照 | Sec. 5.1；Table 4 | evidence/novelty | experiment | baseline matrix、统一预算、PatchTST/iTransformer、GKD/SEED | ccf-experiment-designer | 若排名稳定，Evidence +1 |
| C8 | moderate | 宇宙过窄且策略强烈 long-biased | Table 2；Fig. 6 | significance/generalization | experiment | 扩展行业、股票、熊市/横盘、cross-sectional splits | ccf-experiment-designer | Significance/External validity +1 |
| C9 | moderate | validation/diagnostic 指标不一致 | Tables 4/6/7/9 的 1.81/1.92/1.28 | clarity/evidence | writing | 明确每个窗口日期、用途、配置和 selection relation | ccf-paper-writer | Clarity +1；若实为同窗冲突则 Evidence -1 |
| C10 | moderate | 缺 MAD-OPD 与 SERL | public search | novelty | related-work | 加入 technical comparison/direct baseline | ccf-literature-searcher | Novelty 3->4 的必要非充分条件 |
| C11 | moderate | Fig. 1 使用无来源 backtest/live bars | p. 1 Fig. 1 | clarity/integrity | writing | 标 schematic 或补可核验来源 | ccf-paper-writer | 降低 reviewer-facing risk |
| C12 | minor | 图过密、术语漂移 | Figs. 1-3；Appendix | clarity | writing | 简化图、统一 glossary | ccf-paper-writer | Clarity 3->4 的一部分 |

## 12. AC / Meta-Review

Reviewer consensus 是：问题有价值、框架 chronology 有潜力，但当前稿件的决定性瓶颈是实证有效性。争议不在“系统是否复杂”，而在“复杂系统的哪一部分有效、结果是否无泄漏、主指标是否计算正确”。最强接收理由是 finance-specific delayed-outcome OPD integration；最强拒绝理由是两个会独立推翻中心结论的问题：foundation-model temporal contamination 未排除，以及 macro-average per-asset risk metrics 被误称为 portfolio results。

AC 不应让较好的写作和丰富表格抵消 fatal evaluation risk。即使作者在 rebuttal 中解释 Table 1 是 macro-average，也不能把它变成组合 Sharpe/Calmar；即使声称 input point-in-time，也不能证明 2026 checkpoint 的 weights 不含 2025 信息。这两项需要重新实验而非文字澄清。当前建议 Reject；若文件作为正式投稿，还应先因 anonymity violation 走 desk-reject 检查。

## 13. Quantitative Scores

### Scorecard

| Dimension | Score (1-5) | Confidence (1-5) | Evidence basis | Deduction / score-change condition |
|:---|:---:|:---:|:---|:---|
| Novelty | 3 | 4 | Intro/Related Work；SEED/MAD-OPD/SERL | finance integration 有新意，但算法 delta 未隔离且近邻不全；direct baselines 后可到 4 |
| Soundness | 2 | 4 | Eqs. (5)-(14)；test/model dates | cutoff 风险、utility/router/teacher target 未闭合；重做 temporal-safe protocol 并补定义后可到 3-4 |
| Evidence | 2 | 5 | Tables 1-9；Sec. 5.1 | portfolio metric 错标、单 run/单路径、无 CI、无 held-out factorial ablation；全套重做后可到 4 |
| Significance | 4 | 4 | Problem setup；KDD fit | 金融 agent 真实 outcome learning 重要；但当前只覆盖 4 mega-cap，扩展后可稳定为 4 |
| Clarity | 3 | 5 | 全文与图表 | 主线清楚，但 claims/术语/windows 混乱；统一并纠正可到 4 |
| Reproducibility | 2 | 5 | Appendix A-B | 参数仅部分公开，缺数据/utility/prompts/artifact；可运行 artifact 后可到 4 |
| Ethics / Limitations | 3 | 4 | pp. 8、11-12 | 局限披露好，但数据许可和模型污染未审计；data/model cards 后可到 4 |

**Overall:** 3/10 | **Scholarly Confidence:** 4/5

**Recommendation:** reject

**Verdict:** 修复匿名仅消除 desk reject；若同时解决 cutoff-safe evaluation、真实 portfolio metrics、统计可靠性和 held-out factorial ablation，整体可从 3 提升到 5-6。若确认 foundation model 或视觉/news 数据包含测试期信息，则应降至 1-2。

### Compact Summary

- Quality: 2/5
- Clarity: 3/5
- Significance: 4/5
- Originality: 3/5
- Soundness: 2/5
- Evidence: 2/5
- Reproducibility: 2/5
- Ethics / Limitations: 3/5
- Overall: 3/10
- Confidence: 4/5
- Score-change conditions: 以重新实验为主；仅润色或补解释不足以改变结论。

### Writing Scorecard

| Dimension | Weight | Score (1-5) | Confidence | Evidence basis | Concrete repair |
| --- | ---: | ---: | ---: | --- | --- |
| Storyline and motivation | 12 | 4 | 5 | Intro pp. 1-2 | 保留 chronology，删无来源动机图数据 |
| Contribution display | 12 | 3 | 5 | contribution bullets | 把 integration delta 与已有 OPD 分开 |
| Paragraph logic | 10 | 4 | 5 | 全文 | 主要为局部压缩问题 |
| Claim-evidence alignment | 14 | 2 | 5 | Abstract/Table 1/Fig. 1 | 修正 post-cutoff 与 portfolio claims |
| Method readability | 10 | 2 | 4 | Sec. 4 | 定义 U、D_eta、router probability 与 guards |
| Experiment narration | 10 | 3 | 5 | Sec. 5 | 增加 split/metric map，区分 test/diagnostic/validation |
| Related-work positioning | 8 | 3 | 4 | Sec. 2 | 加 MAD-OPD/SERL 和逐轴比较 |
| Terminology consistency | 8 | 2 | 5 | Belief/memory、U/J、threshold notation | 统一 glossary/notation |
| LaTeX and format discipline | 8 | 1 | 5 | p. 1/headers | 必须匿名化并移除 camera-ready 元数据 |
| Reviewer-facing risk | 8 | 1 | 5 | 两个 fatal scientific issues | 先重做证据，再改文案 |

**Weighted writing score:** 2.58/5

**Writing risk band:** severe（主要由匿名违规和 claim-evidence mismatch 驱动，不代表英文语法差）。

### Score-Change Conditions

| Change | Condition | Likely affected dimensions | Expected movement |
| --- | --- | --- | --- |
| Raise score | cutoff-safe backbone + synchronized portfolio PnL + multi-cycle/statistical test | Soundness, Evidence | +1 to +2 overall |
| Raise score | held-out factorial OPD/memory/credit/router/guard ablation + direct OPD baselines | Novelty, Evidence | +0.5 to +1 overall |
| Lower score | 证实 backbone/data 含测试期信息或 Table 1 无法重算 | Soundness, Evidence, Integrity | -1 to fatal |
| No quick change | 扩展市场周期、资产宇宙和重复训练 | Generalization, Evidence | submission 前若无计算资源则难完成 |

## 14. Questions For Authors

1. Qwen3.5-9B 的具体 checkpoint hash、训练数据 cutoff 和 release date 是什么？如何证明其 weights 不包含 2025-01 至 2026-02 的公司事件、新闻或市场叙事？
2. Table 1 是否只是 Table 2 四资产 CR/SR/Calmar 的算术平均？若是，为什么称作 portfolio/aggregate results？能否提供 synchronized daily portfolio return series？
3. Scalar utility `U`/`J`的完整公式、归一化、权重和选择过程是什么？它如何影响 router、memory、credit 和 teacher prompt？
4. Teacher 只观察 executed action 的 outcome 时，如何得到对 alternative action 有意义的 token distribution？“hindsight teacher upper bound”为什么是上界？
5. Eq. (5) 中 Gumbel top-k subset 的 `log P_psi(I_t|...)`具体如何计算和反向传播？
6. Table 4 的 SR 1.81、Tables 6/7 的 1.92 和 Table 9 的 1.28 分别对应哪些准确日期、股票、配置和 selection role？
7. 为什么 PatchTST/iTransformer、vanilla GKD/OPD、uniform credit、w/o reference KL 没有出现在主 held-out comparison？
8. 50k weak charts、1k verified charts、news/filings 和 OHLCV 的来源、时间范围、许可、修订/发布时间处理和测试重叠情况是什么？
9. Baseline 的版本、prompt、hyperparameter budget、随机种子和 allocation adaptation 是什么？所有方法是否获得相同 tuning budget？
10. zero exposure 的收益方差为零时，Table 5 为什么把 Sharpe 记为 0.00，而不是 undefined/N/A？

## 15. Score Revision Criteria

**Raising the score would require:**

1. 立即匿名化并通过 KDD format check；
2. 使用无争议 pre-test cutoff 模型和数据重跑；
3. 从真实同步组合日收益重算所有 portfolio metrics；
4. 在多个独立周期/资产和多个 seeds 上给出 CI 与多重比较校正；
5. 在 held-out test 上完成 OPD、memory、credit、router、reference KL 和 execution guard 的 factorial ablation；
6. 补齐 utility、router estimator、allocator、prompts、数据卡、baseline configs 和匿名 artifact。

**Lowering the score would be triggered by:**

- model/data contamination 被确认；
- 主表无法由原始 daily PnL 重算；
- baseline 使用了不等价输入、调参预算或 execution constraints；
- factor/chart/news 数据与 test overlap 且未隔离。

**Concerns unlikely to change before submission:**

- 若没有现成历史 run，扩展独立市场周期和 3-5 个 seeds 需要实质计算；
- 17 个月路径本身无法通过写作变成独立重复样本；
- 当前 appendix 的 diagnostic results 不能通过改名替代 held-out causal evidence。

## 16. Action Plan And CCFA Handoffs

### Priority P0

- **Action:** 生成完全匿名的 KDD review PDF，核对 8 页正文、作者信息、页眉、metadata、链接和 camera-ready 占位。
- **Owner skill:** ccf-submission-checker
- **Input needed:** TeX source / Overleaf export
- **Expected output:** anonymity + format audit and clean review PDF
- **Handoff required:** yes

### Priority P0

- **Action:** 审计 Qwen/data cutoff，选择 cutoff-safe backbone 或后移测试期，建立 contamination tests。
- **Owner skill:** ccf-experiment-designer
- **Input needed:** checkpoint hashes、model cards、data manifests、timestamp policies
- **Expected output:** temporal-integrity protocol and rerun matrix
- **Handoff required:** yes

### Priority P0

- **Action:** 从 synchronized daily PnL 重算真实组合 CR/SR/MDD/Calmar，并做 block bootstrap。
- **Owner skill:** ccf-experiment-designer
- **Input needed:** 每方法每资产每日 position、return、cost、cash、portfolio weights
- **Expected output:** corrected main tables with uncertainty
- **Handoff required:** yes

### Priority P1

- **Action:** 设计 held-out factorial ablation 与强基线矩阵。
- **Owner skill:** ccf-experiment-designer
- **Input needed:** 训练代码、算力预算、现有 checkpoints
- **Expected output:** OPD/memory/credit/router/guard causal evidence
- **Handoff required:** yes

### Priority P1

- **Action:** 补齐 MAD-OPD、SERL、SEED 的逐轴定位及 direct comparison。
- **Owner skill:** ccf-literature-searcher
- **Input needed:** 当前 Related Work 与实验代码能力
- **Expected output:** verified comparison table and baseline recommendations
- **Handoff required:** yes

### Priority P2

- **Action:** 在新结果稳定后重写摘要、Fig. 1、Table 1 caption、实验叙事、结论和术语表。
- **Owner skill:** ccf-paper-writer
- **Input needed:** 修正后的结果、split map、method definitions
- **Expected output:** evidence-aligned KDD manuscript text
- **Handoff required:** yes

**Checks run:** 12 页全文提取；逐页视觉渲染；PDF metadata/JavaScript/form/encryption 检查；主表算术交叉核验；claim-evidence audit；KDD 2027 官方格式/匿名规则；公开近邻搜索；Qwen 官方发布时间与模型卡核验；多 reviewer 与 AC 综合。

**Checks skipped:** 未取得 TeX source，故未编译或检查 citation keys/labels/overfull boxes；未取得代码、raw daily PnL、data manifests 和 checkpoints，故未复现实验或验证实际泄漏。

**Unresolved risks:** foundation-model/data contamination；真实 portfolio ranking；baseline implementation fairness；utility/prompt/router estimator；多周期统计可靠性；数据许可与 timestamp integrity。
