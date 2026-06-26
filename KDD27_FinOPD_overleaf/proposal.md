# Title
FinOPD: 面向金融多智能体交易系统的在策略自蒸馏与边际优势门控自进化框架
 
# Abstract
大语言模型驱动的金融多智能体系统正在成为自动化投研和交易决策的重要范式，但现有系统的“自我提升”大多停留在提示词、记忆或自然语言反思层面：交易结果被总结为经验文本，模型参数和因子路由策略并未真正从真实收益反馈中更新。另一方面，直接以涨跌方向准确率或短期预测误差作为训练目标，又容易造成典型的 reward hacking：命中率上升但累计收益、夏普比率和最大回撤恶化。本文拟提出 FinOPD，一个面向金融多智能体交易系统的收益锚定在策略自蒸馏框架。FinOPD 将交易轨迹的事后风险调整收益作为 privileged information，引导同一模型在 student/teacher 双条件下进行 on-policy self-distillation；同时通过 Shapley 式边际贡献估计，为图形分析、模式推理、事件分析、风险控制和组合决策等专门智能体分配差异化学习权重。为解决金融市场非平稳和样本稀缺问题，框架进一步引入非参数 belief store，将高收益轨迹中的“图形几何 - 因子子集 - 动作 - 收益”四元组在线沉淀为可检索交易知识，并通过 Geometry-Conditioned Factor Router 在 160+ 候选 alpha 因子中选择与当前市场结构匹配的因子集合。在决策层，FinOPD 使用 Regime-Adaptive Signal Weighting 和 Edge-Gated Abstention，使系统只在趋势、波动或因子一致性提供可度量边际优势时建仓，而在无优势区间主动 abstain。该框架旨在把金融 LLM agent 从 prompt-level verbal reinforcement 推进到 policy-level self-evolution，并在严格 post-cutoff、含交易成本、滑点和 T+1 执行延迟的协议下验证其风险调整收益、跨市场状态稳健性和抗信息泄漏能力。

### 动机、挑战和对应的解决方案
研究动机。 金融交易天然是高噪声、非平稳、长反馈链条的序列决策问题。LLM 多智能体系统能够把技术面、事件面、风险控制和组合管理拆解给不同角色，并用自然语言形成可解释决策链；FinCon、FinMem、TradingAgents、FinAgent 等工作已经证明多角色协作、记忆和反思对金融决策有价值。然而，现有系统的关键缺口在于：它们多数只把经验写回 prompt 或 memory，参数、因子选择器和决策阈值并未通过真实 PnL 闭环更新。因此，系统看似“会反思”，但并不等价于策略会进化。

为了让文章主线更集中，建议全文只围绕 两个核心挑战 展开。其他内容，例如视觉几何编码、因子库、belief store、信息泄漏诊断，都应作为支撑机制或评测协议出现，而不是并列成新的挑战。

挑战 1：如何让金融多智能体系统从真实交易结果中自进化，而不是停留在语言反思或方向预测？

核心矛盾：金融交易没有像数学题或代码题那样稳定的标准答案，直接用涨跌方向、IC 或分类准确率做训练目标，会把系统推向 prediction-centric 的 reward hacking；同时，一次交易收益由图形分析、因子信号、事件理解、风险控制和 PM 决策共同产生，若不做信用分配，参数更新会奖励错对象或稀释真正有效的 agent。
对应方案：提出 Profit-Anchored On-Policy Self-Distillation。用事后 K 日风险调整 PnL（Sharpe、Sortino、MDD、CVaR、成本后收益）作为 privileged teacher signal；student 只看交易当时可得信息，teacher 额外条件化 hindsight PnL；通过 token/action-level JSD 或 KL 将收益导向的策略偏好蒸馏回 LoRA 参数。同时，用 Shapley 式 leave-subset-out replay 估计各 agent 的边际贡献，对蒸馏 loss 加权。
论文写法：这一挑战可以同时覆盖“优化目标错位”和“多智能体信用分配”两个技术点，但不要拆成两个挑战。它对应本文的学习层贡献：hindsight-PnL conditioning + on-policy distillation + Shapley credit。
挑战 2：如何在非平稳市场中只在有可交易优势的状态下行动，而不是让自进化策略被无优势区间和交易成本吞噬？

核心矛盾：金融 alpha 不是全局稳定存在的。图形形态、因子组合和多智能体推理只在特定 regime 下有效；如果系统每天强制给出 buy/sell，calm/no-edge 区间的频繁交易会用成本和滑点抹掉少量 alpha。换言之，交易系统不仅要学“怎么判断方向”，更要学“什么时候不下注”。
对应方案：提出 Regime-Aware Edge-Gated Policy。Geometry-Conditioned Factor Router 根据当前图形结构和 regime 选择因子子集；belief store 检索相似历史结构，用于估计当前模式是否曾经产生可交易收益；Regime-Adaptive Signal Weighting 根据趋势、波动和均值回复状态动态调整信号权重；Edge-Gated Abstention 在 edge score 不足时输出零仓位，把 abstention 作为显式策略动作。
论文写法：这一挑战把“市场非平稳”“因子/图形适用性”和“何时交易”合并为一个问题。它对应本文的决策层贡献：factor routing + belief retrieval + RASW + EGA。
不建议作为主挑战、但可以保留的位置。

信息泄漏、幸存者偏差、post-cutoff 测试：放在 evaluation protocol，作为可信度保障，而不是方法挑战。
视觉几何编码：放在 architecture/infrastructure，说明它提供可结构化、可检索、可路由的市场状态表示，而不是单独声称为挑战。
belief store 的灾难性遗忘问题：作为挑战 2 的支撑机制，强调它帮助判断当前结构是否有历史 edge。


### 提出概念和整体方法介绍
本文建议把核心概念统一为：收益锚定的金融策略自进化（Profit-Anchored Financial Policy Self-Evolution）。

该概念包含两层含义：

从 verbal reflection 到 profit-anchored policy evolution。 现有金融 agent 主要通过自然语言反思改善下一次 prompt。FinOPD 将轨迹收益回传到 LoRA 参数和多智能体决策分布，使训练目标从方向预测转向风险调整收益。
从 always-trade 到 regime-aware selective trading。 系统不仅学习“买/卖什么”，还学习“什么时候不下注”。在金融场景中，abstention 是一种主动风险管理策略，而非缺省的 Hold。
整体架构建议分为五个模块：

Visual-Geometric Encoder（结构化图形感知）

输入：60 日或多尺度 K 线图、OHLCV、成交量、技术指标 overlay。
输出：结构化 ChartGeometry JSON，包括趋势线、支撑阻力、形态、蜡烛图组合、成交量背离、波动状态等。
作用：把视觉图形转为可验证、可路由、可检索的中间表示，避免黑箱图像 prompt。
Geometry-Conditioned Factor Router（图形条件化因子路由）

输入：ChartGeometry embedding、regime one-hot、候选因子库。
输出：top-k 因子集合，供多智能体共享。
学习方式：用 Gumbel-Softmax/GRPO-lite 或 bandit update 根据风险调整 PnL 更新路由策略。
Financial Multi-Agent Decision Layer（金融多智能体决策层）

角色：ChartAnalyst、PatternReasoner、EventAnalyst、RiskController、DecisionPM。
协作：共享记忆中注入图形结构、因子值、belief retrieval、事件上下文和风险预算。
输出：动作 Buy/Sell/Hold/Abstain、仓位、止损止盈、自然语言 rationale。
On-Policy Self-Distillation with Hindsight PnL（事后收益条件化在策略自蒸馏）

student：只看到当前观测和历史可得信息。
teacher：在相同轨迹 token 上额外条件化事后 K 日风险调整收益。
loss：token-level generalized JSD/KL，乘以轨迹级收益权重和 agent-level Shapley 权重，并加入 KL guard 防止策略漂移。
Online Belief Store and Edge-Gated Policy（在线知识蒸馏与优势门控策略）

belief store：只接纳高收益/低回撤轨迹中的四元组 (geometry, factors, action, risk-adjusted PnL)。
online distillation：推理时检索相似结构作为 few-shot priors；训练时将高质量 belief 转为 distillation batch。
EGA：根据 regime 和信号一致性控制是否交易，低 edge 状态默认 abstain。


### 方法Outline
1. 问题定义
给定资产集合、交易日序列和多模态观测 o_t = (I_t, X_t, D_t)：

I_t：K 线图及技术 overlay。
X_t：OHLCV、因子矩阵、市场状态特征。
D_t：新闻、财报、公告、宏观事件等文本。
多智能体系统输出 a_t = (direction_t, size_t, risk_t, rationale_t)，目标是在成本、滑点、执行延迟和风险预算约束下最大化：

E[J(tau)] = E[Sharpe + lambda_1 Sortino - lambda_2 MDD - lambda_3 CVaR - lambda_4 TurnoverCost]。

2. 图形结构编码
用规则几何提取器生成弱标签：趋势线、支撑阻力、突破/跌破、头肩/三角/箱体、量价背离。
用 VLM/多模态基础模型进行 LoRA SFT，输出严格 schema 的 ChartGeometry JSON。
加入 schema validator 和 rejection sampling，确保几何字段可用于后续 factor router 和 belief retrieval。
3. 因子库与因子自进化
初始因子库由三类组成：经典技术指标、101/WorldQuant 风格公式因子、LLM/搜索生成因子。
每个因子记录：表达式、输入字段、lookback、行业/市场适用性、IR、turnover、相关性、稳定性和解释。
因子自进化采用“生成 - 静态检查 - 回测 - 去相关 - 入库”的闭环：
factor proposer 生成候选表达式；
grammar/type checker 保证语法、维度、无未来函数；
walk-forward backtest 计算风险调整指标；
与现有因子做相关性惩罚；
仅将高 IR、低相关、跨 regime 稳定的因子加入候选池。
与 FinOPD 的连接点：router 不必重新生成因子，而是在当前几何和 regime 下选择“此时可用”的因子子集。
4. 多智能体协作与信用分配
每个 agent 产生结构化输出：claim、evidence、confidence、risk_flag、action_hint。
DecisionPM 汇总为最终动作，RiskController 有 veto/scale-down 权限。
对高收益和高损失轨迹都做 replay：高收益轨迹用于正向蒸馏，高损失轨迹用于反事实/负偏好样本。
Shapley 近似：随机采样 agent 子集，比较有/无某 agent 输出时的 J(tau) 或 proxy score，得到贡献 phi_i。
5. 事后收益条件化在策略自蒸馏
student 分布：p_S(y | o_t, memory, factors)。
teacher 分布：p_T(y | o_t, memory, factors, hindsight_J)。
teacher 不需要外部专家，可由同一基础模型在 privileged PnL 条件下产生更贴近收益目标的解释和动作偏好。
蒸馏目标：
token-level JSD/KL 对齐推理文本和决策 JSON；
action-level CE/DPO 对齐 Buy/Sell/Hold/Abstain；
size/risk head 用 MSE/Huber 对齐仓位和止损；
加 KL-to-reference guard 限制模型偏离初始策略。
6. 非参数 belief consolidation
入库规则：J 超过滚动 80 分位，且 MDD/CVaR 不超过风险预算。
检索键：ChartGeometry embedding + regime + factor signature。
检索值：历史相似图形、当时因子组合、动作、收益、失败边界、解释。
遗忘机制：容量上限、低收益淘汰、regime 均衡采样，避免 belief store 被单一牛市模式污染。
7. Regime-Adaptive Signal Weighting 与 Edge-Gated Abstention
regime 识别：20/60 日实现波动、趋势斜率、成交量冲击、横截面相关性、市场宽度。
RASW：在趋势市提高 trend/factor 权重，在震荡高波动提高 mean-reversion/risk 权重，在 calm/no-edge 市降低整体交易倾向。
EGA：若 edge_score = f(signal_consensus, regime, retrieved_belief_quality, factor_IR) 低于阈值，则输出 Abstain/zero position。
论文表达建议：把 EGA 从普通 Hold 区分开，强调它是“selective prediction/trading”的金融化实现。
8. 安全与部署约束
强制 position limit、daily turnover limit、sector exposure limit、kill switch。
所有实验输出都保存 agent trace、factor snapshot、data timestamp 和 commit hash。
不把本文定位为可直接自动实盘部署，而定位为 institutional research prototype。

### 实验内容Outline
实验看板以todo_exp.sh统一维护,里面每一行以"nohup bash run_xxx.sh > ./run_xxx.log 2>&1 &"加上中文注释的形式呈现。

nohup bash experiments/run_main_finopd.sh > ./logs/run_main_finopd.log 2>&1 &  # 主实验：完整 FinOPD，在 post-cutoff 测试集上报告 CR/SR/MDD/WR/turnover
nohup bash experiments/run_baselines_finopd.sh > ./logs/run_baselines_finopd.log 2>&1 &  # 基线对比：Buy&Hold、Equal-Weight、PatchTST、iTransformer、TradingAgents、FinCon、FinAgent、R&D-Agent
nohup bash experiments/run_ablation_learning_layer.sh > ./logs/run_ablation_learning_layer.log 2>&1 &  # 学习层消融：去除 OPSD、去除 Shapley、去除 hindsight PnL、改用方向准确率蒸馏
nohup bash experiments/run_ablation_decision_layer.sh > ./logs/run_ablation_decision_layer.log 2>&1 &  # 决策层消融：去除 RASW、去除 EGA、固定阈值、固定信号权重
nohup bash experiments/run_ablation_belief_store.sh > ./logs/run_ablation_belief_store.log 2>&1 &  # 记忆消融：无 belief、随机 belief、只检索不入库、不同容量和入库分位数
nohup bash experiments/run_factor_router.sh > ./logs/run_factor_router.log 2>&1 &  # 因子路由：top-k、Gumbel 温度、因子相关性约束、router vs fixed factor set
nohup bash experiments/run_factor_evolution.sh > ./logs/run_factor_evolution.log 2>&1 &  # 因子自进化：候选因子生成、静态检查、回测去相关、入库质量曲线
nohup bash experiments/run_regime_analysis_finopd.sh > ./logs/run_regime_analysis_finopd.log 2>&1 &  # 分市场状态：trending/volatile/normal/calm 的 SR、MDD、abstention rate
nohup bash experiments/run_counterfactual.sh > ./logs/run_counterfactual.log 2>&1 &  # 反事实诊断：去图表、打乱日期、随机财务数值、替换新闻，验证信号来源
nohup bash experiments/run_sensitivity.sh > ./logs/run_sensitivity.log 2>&1 &  # 超参敏感性：edge threshold、position size、belief top-k、factor top-k、KL budget
nohup bash experiments/run_evolution_curve.sh > ./logs/run_evolution_curve.log 2>&1 &  # 自进化轨迹：每轮 OPSD 后 SR/MDD/belief hit-rate/router entropy 的变化
nohup bash experiments/run_cost_latency.sh > ./logs/run_cost_latency.log 2>&1 &  # 效率分析：GPU 小时、推理延迟、API 成本、每资产每日耗时
nohup bash experiments/run_leakage_protocol.sh > ./logs/run_leakage_protocol.log 2>&1 &  # 泄漏控制：pre-cutoff vs post-cutoff、rolling split、purged walk-forward 对比

### Reference
1. https://github.com/georgezouq/awesome-ai-in-finance
2. https://github.com/RKiding/Awesome-finance-skills
3. https://github.com/icoxfog417/awesome-financial-nlp
可以从上述仓库入手找到值得参考的文章，或者自行调研金融量化系统+模型训练方向的文章

On-Policy Distillation / GKD: https://openreview.net/forum?id=3zKtaqxLhW
DPO: https://arxiv.org/abs/2305.18290
DeepSeekMath / GRPO: https://arxiv.org/abs/2402.03300
InstructGPT / RLHF: https://arxiv.org/abs/2203.02155
DAgger: https://arxiv.org/abs/1011.0686
Policy Distillation: https://arxiv.org/abs/1511.06295
TradingAgents: https://arxiv.org/abs/2412.20138
FinAgent: https://arxiv.org/abs/2402.18485
FinCon: https://arxiv.org/abs/2407.06567
FinMem: https://arxiv.org/abs/2311.13743
R&D-Agent-Quant: https://arxiv.org/abs/2505.15155
DeepFund live benchmark: https://arxiv.org/abs/2505.11065
FINSABER long-run evaluation: https://arxiv.org/abs/2505.07078
Qwen2.5-VL: https://arxiv.org/abs/2502.13923
101 Formulaic Alphas: https://arxiv.org/abs/1601.00991
RiskMiner: https://arxiv.org/abs/2402.07080
Alpha^2: https://arxiv.org/abs/2406.16505
AlphaCFG: https://arxiv.org/abs/2601.22119

### 实验信息
conda环境/screen窗口指定: FinOPD
训练框架: ms-swift (本地路径../ms-swift)
火山云代理加速：export ALL_PROXY=<PROXY_URL>
benchmark: 
metrics：
github账号: <REDACTED>
仓库/目前分支: [FinOPD/exp_0613分支](https://github.com/RWLinno/FinOPD/tree/exp_0613)
github token:<REDACTED>
hf token: <REDACTED>
wandb 项目:finopd  API KEY: <REDACTED>
所有实验以todo_exp.sh作为看板，每一行以"nohup bash run_xxx.sh > ./run_xxx.log 2>&1 &"的形式出现。

### TBD
20260528: 确认文章框架，开始设计实验计划和执行实验
20260607: 继续跑实验，将真实结果填入latex表格中，并且修改文章对应的结果分析。同时把中文的结果观察、具体分析和结论详细记录在markdown中。
20260625: 需要你比较多个版本，充分丰富实验部分。然后进行大规模的latex润色，直到文章完成度足以投稿。