# FinOPD 实验计划 Prompt

> 本文档为完整的实验执行指令，直接复制给实验窗口的 coding agent 使用。

---

## Role

资深 ML 工程师 + 量化研究员，熟悉 PyTorch、Transformers、PEFT/LoRA、ms-swift、vLLM、FAISS 与金融回测工程。

## Context

在 `FinVL-MAS` 仓库（GitHub: https://github.com/RWLinno/FinVL-MAS/，当前分支 v3，目标分支 exp_May21）上实施 KDD 2027 投稿实验。项目已更名为 **FinOPD**（Financial On-Policy Distillation），核心贡献是经验驱动的双轨自进化机制。

仓库现有：5 agent 骨架（ChartAnalyst / PatternReasoner / EventAnalyst / RiskController / DecisionPM）、门控共享记忆、规则几何提取器、回测器与合成数据 pipeline 已跑通。

关键升级：On-Policy Self-Distillation（参数侧）+ Long-Term Belief Consolidation（非参数侧）+ Visual-Geometric Encoder + Factor Router。

## 环境与凭证

```bash
# 创建 conda 环境
conda create -n finopd python=3.10 -y
conda activate finopd

# 网络代理（如果网络不通）
export ALL_PROXY=http://accelerator-cname-hnpmnhnmdul3rmxrwhgend.c.vegalb.com:80

# HuggingFace（数据和模型 checkpoint 上传）
export HF_TOKEN=${HF_TOKEN}

# Wandb 实验监控
export WANDB_API_KEY=${WANDB_API_KEY}

# 训练框架
pip install ms-swift[all]
```

## 自进化挖掘因子库

路径: `docs/best_factor.json`，约 160 个因子，IR 最高达 3.04（RESI_ZSCORE_6_5）。这些因子已经过自进化挖掘验证，直接作为 Factor Router 的候选因子库使用。

## Git 分支管理

```bash
git checkout v3
git checkout -b exp_May21
git push -u origin exp_May21
```

## Overall Objective

完成端到端实现，最终目标是以下脚本单命令跑通：

```bash
bash experiments/run_all.sh --data data/processed/us_dow30.csv --mode full
```

## Coding Principles

- 所有新模块配 pytest 单元测试（覆盖率 70%+）
- 所有 pipeline 通过 YAML 配置切换（禁止 hard-code 超参）
- 所有随机种子可固定且主实验至少 3 seed 平均
- 日志用仓库现有 `src/finvl/utils/logging.py`
- 实验产物写到 `outputs/experiments/YYYY-MM-DD_<exp_name>/`
- Git commit 粒度细（每个 Stage 至少 3 个可 review 的 commit）
- 训练框架优先使用 ms-swift

---

## Stage 1 — Data and Annotation Infrastructure (Day 1-2)

### 1.1 数据扩展

扩展 `data/pipeline.py` 至 Dow-30 规模 25 支美股 + CSI300 子集 10-15 支：
- 美股: yfinance OHLCV + 已有新闻/财报数据源
- A股: Tushare 高流动性标的

### 1.2 ChartGeometry 数据集构建

新建 `src/finvl/datasets/chart_geometry/build.py`：
- 在 2015-2022 训练窗口每日渲染一张 60 日 lookback K 线图
- 调用现有规则几何提取器 `src/finvl/visual/geometry.py` 生成 ChartGeometry JSON
- 字段: `trend_lines[]`, `price_levels[]`, `candle_patterns[]`, `chart_formations[]`, `volume_signals[]`, `regime`
- 目标 50k 样本，输出 JSONL: `{image_path, geometry_json, ticker, date}`

### 1.3 标注验证工具

新建 `src/finvl/datasets/chart_geometry/human_verify_tool.py`：
- 最小化 Gradio 标注界面
- 从 50k 随机抽 1000 张对 pattern 与 regime 字段做 approve/edit/reject

### 1.4 Cutoff 配置

新建 `configs/cutoffs.yaml`：
```yaml
model_cutoffs:
  qwen2.5-vl-7b: "2024-03"
  gpt-4o-mini: "2024-10"
  deepseek-v3: "2024-12"
test_start: "2025-01-01"
live_forward_start: "2026-05-01"
```

### 产物
- `data/processed/us_dow30.csv`, `data/processed/csi300_subset.csv`
- `data/chart_geometry/train.jsonl` (~50k)
- `configs/cutoffs.yaml`

---

## Stage 2 — Visual-Geometric Encoder (Day 3-5)

### 2.1 LoRA 训练

在 `src/finvl/visual/vlm_lora/train.py` 实现基于 ms-swift 的 Qwen2.5-VL-7B LoRA 训练：
- rank=16, target_modules: vision encoder 末层 + cross-attention
- 使用 ms-swift 的 sft 接口进行训练

### 2.2 Instruction 格式

System prompt 要求严格 JSON 输出：
```json
{
  "trend_lines": [...],
  "price_levels": [...],
  "candle_patterns": [...],
  "chart_formations": [...],
  "volume_signals": [...],
  "regime": "trending|ranging|volatile|calm"
}
```
用 jsonschema 做 reject sampling，目标合规率 >98%。

### 2.3 评估

在干净验证集上报告 pattern 级 recall/precision 与 regime 准确率，写入 `outputs/vlm_lora_eval.json`。

### 2.4 推理接口

封装 `geometric_encoder.encode(image_path) -> ChartGeometry` 供下游复用。

### 产物
- LoRA checkpoint: `outputs/vlm_lora/`
- 评估报告: `outputs/vlm_lora_eval.json`
- 推理接口可调用

---

## Stage 3 — Factor Router and MVP Run (Day 6-8)

### 3.1 因子库实现

在 `src/finvl/factors/library.py`：
- 从 `docs/best_factor.json` 加载 ~160 个自进化挖掘因子
- 补充 pandas_ta 覆盖的传统因子（RSI, MACD, Bollinger 等）
- 新建 `src/finvl/factors/geometric.py` 实现几何因子（形态 payoff、趋势一致性投票、归一化 S-R 距离、regime-conditioned 波动）

### 3.2 Router 实现

在 `src/finvl/factors/router.py`：
- 输入: `(geometry_embedding, regime_onehot)`
- 结构: 2 层 MLP + gumbel-softmax top-k (k=10~20)
- 输出: 因子 ID 列表与调用参数

### 3.3 Orchestrator 集成

修改 `src/finvl/workflow/orchestrator.py` 使 5 专家 agent 消费 Router 的因子结果。

### 3.4 MVP 检查点

跑通 `experiments/run_mvp.sh`，在测试集上得到 A1（不含自进化）的主实验数字。如已能超过 TradingAgents 与 FinCon，则即使 Stage 4 受阻仍可作为 MVP 论文提交。

### 产物
- 因子库可调用
- Router 可训练
- MVP 端到端结果

---

## Stage 4 — Experience-Driven Self-Evolution (Day 9-14)

这是 FinOPD 的核心实验，分参数侧与非参数侧两条路径。

### 4A. 参数侧：On-Policy Self-Distillation

#### 4A.1 Teacher Forward

`src/finvl/self_evolution/opsd/teacher.py`:
- Teacher 与 Student 共享同一套 LoRA 权重
- Teacher prompt 前置 `[HINDSIGHT] <serialized_risk_adjusted_returns>` 作为特权信息
- Teacher 一次前向得到整条 student trajectory 上每个位置的 logits 分布
- Teacher 权重整训练期冻结为 initial LoRA checkpoint

#### 4A.2 JSD Loss

`src/finvl/self_evolution/opsd/jsd.py`:
- 广义 JSD: `jsd(p_T, p_S, beta=0.5)`
- Per-token KL clipping: `per_token_kl_clip(logits_T, logits_S, cap=c)`
- 避免风控/建议类 stylistic tokens 主导梯度

#### 4A.3 Student Rollout

`src/finvl/self_evolution/opsd/rollout.py`:
- 滚动窗口轨迹采样
- 每条轨迹记录 `(o_t, y^(i)_t, a_t)` 与 post-hoc 的 `(Sharpe, MDD, CVaR, Sortino)`

#### 4A.4 Shapley Credit

`src/finvl/self_evolution/credit/shapley.py`:
- 每条高分轨迹随机采样 m=8 个 agent 子集做 leave-subset-out 重放
- 估计每个 agent 的边际贡献归一化作为蒸馏样本权重

#### 4A.5 GRPO-lite for Router

`src/finvl/self_evolution/grpo_lite/router_update.py`:
- 当前 mini-batch 轨迹的 (J - mean(J)) 作为离散因子选择的 advantage
- 不需要 critic

#### 4A.6 Alignment Guard

`src/finvl/self_evolution/guard/alignment.py`:
- 每步检查 KL(student || reference) < epsilon 否则回退
- 每 4 轮用 2020 COVID / 2022 熊市 / 极端波动日的对抗样本做 off-policy refresh

### 4B. 非参数侧：Long-Term Belief Consolidation

#### 4B.1 四元组抽取

`src/finvl/self_evolution/belief/extractor.py`:
- 从高分轨迹（J 高于 80 分位）抽取 `(geometry_signature, factor_set, action_pattern, realized_J)`
- geometry_signature = VLM 末层几何 token 的 mean-pooling 向量

#### 4B.2 向量索引

`src/finvl/self_evolution/belief/index.py`:
- 基于 FAISS 的 geometry embedding 向量索引
- 支持增量写入与 capacity 约束

#### 4B.3 推理时检索

`src/finvl/self_evolution/belief/retrieval.py`:
- 对当前 geometry_signature 做 top-k 近邻查询
- 命中的 (factor_set, action_pattern) 以 few-shot 先验注入共享记忆

#### 4B.4 Evolution Curve Logger

`src/finvl/self_evolution/curves/logger.py`:
- 每轮迭代 k 后记录 `{k, val_sharpe, val_alpha_decay, belief_size, belief_hit_rate}`
- 输出到 `outputs/self_evolution_curve.jsonl`

### 稳定性验证

先在 AAPL 单资产跑 3 个参数侧 epoch 做稳定性验证：
- 若 KL 爆炸或 PnL 负向蒸馏 → 启动 Plan C（仅保留非参数侧）
- 通过后扩展到 Dow-30 全量

### 产物
- OPSD 训练循环可运行
- Evolution curve 数据
- Belief 库快照

---

## Stage 5 — Evaluation Rigor Protocol and Main Experiments (Day 15-18)

### 5.1 Cutoff-aware Rollout

`src/finvl/eval/rigor/cutoff_rollout.py`:
- 严格按 `configs/cutoffs.yaml` 过滤测试日期

### 5.2 Counterfactual Perturbation

`src/finvl/eval/rigor/counterfactual.py`:
- 三种扰动: 新闻情感极性反转、报表非关键数字随机化、日期 token 替换
- 度量扰动前后 Sharpe/accuracy 的 delta

### 5.3 Live-Forward Daemon

`src/finvl/eval/rigor/live_forward.py`:
- 每日拉取 yfinance 最新数据跑一次全量推断
- 结果写入 `outputs/live_forward/YYYY-MM-DD.json`

### 5.4 主实验与消融

```bash
experiments/run_ablations.sh  # A1-A10 全量消融
experiments/run_baselines.sh  # 12 个 baselines
```

消融配置 (A1-A10):
| ID | 配置 | 检验问题 |
|----|------|----------|
| A1 | Full FinOPD | 上限 |
| A2 | 移除视觉-几何（退化为文本 MAS） | H1: C1 的价值 |
| A3 | 冻结 VLM（不做 LoRA） | 金融图表对齐的价值 |
| A4 | 移除 Router，改为固定工具模板 | H2: C2 的价值 |
| A5 | 关闭参数侧自进化（保留 verbal reinforcement） | H3 参数侧: OPSD 的价值 |
| A6a | 关闭 Shapley credit（均等权重） | 信用分配的价值 |
| A6b | 关闭非参数侧 belief consolidation | H3 非参数侧: 长期记忆的价值 |
| A7 | 关闭 alignment guard | 漂移防护的必要性 |
| A8 | 单 agent collapse（5 合 1） | 多智能体分解的价值 |
| A9 | 单轮自进化 (k=1) vs 多轮 (k≥3) | H4: 自进化轨迹单调性 |
| A10 | 用 trajectory search 风格自进化替代 OPSD | 方法选型正当性 |

### 产物
- 主实验结果表
- 消融结果
- Evolution curve 图
- 反事实扰动 delta

---

## Stage 6 — Results Upload and Reporting (Day 19-21)

### 6.1 结果上传

```bash
# 上传模型 checkpoint 到 HuggingFace
huggingface-cli upload <your-org>/FinOPD-VLM-LoRA outputs/vlm_lora/
huggingface-cli upload <your-org>/FinOPD-Checkpoints outputs/self_evolution/

# 上传数据集
huggingface-cli upload <your-org>/FinChartGeometry-50K data/chart_geometry/
```

### 6.2 Wandb 报告

确保所有实验在 wandb 项目中有完整记录，包括：
- 训练 loss 曲线
- Evolution curve
- 消融对比

### 6.3 最终报告

生成 `outputs/final_report.html` 可视化所有指标。

---

## Acceptance Criteria（投稿前必须达成）

- **H1**: A2 相对 A1 在 volatile regime 上 accuracy 下降 ≥5pp，Sharpe 下降 ≥0.2
- **H2**: A1 相对 A4 在 token 成本差距 ≤10% 情况下 tool-call 人工评分准确率提升 ≥10pp
- **H3**: A1 相对 A5 在 2025 测试集上 alpha decay 下降 ≥30% 且 live-forward 正向年化净收益；A1 相对 A6b Sharpe 下降 ≥0.15
- **H4**: Evolution curve 在 3 seed 下均呈现单调改进或稳定
- Live-forward 至少跑满 1 个月
- 所有指标在 `outputs/final_report.html` 可视化且可复现

---

## 紧急 Fallback

- **Plan B**: 若 OPSD 参数侧 KL 爆炸 → 仅保留非参数侧 belief consolidation + GRPO-lite Router
- **Plan C (MVP)**: 若自进化全部受阻 → 退为 VGE + Router 的 MVP 系统论文
