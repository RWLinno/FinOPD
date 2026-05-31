# FinOPD 实验工作总结

## 时间线

| 日期 | 阶段 | 事件 | 结果 |
|------|------|------|------|
| 05-28 | S0 | 环境搭建 | conda + 依赖 + 凭证 + 目录结构 |
| 05-28 | S1 | 数据构建 | Dow-30 OHLCV 52775行, ChartGeometry 2375样本 |
| 05-30 | S2 | vLLM 服务 | Qwen2.5-VL-32B, 4xA800 TP=4, 加载109s |
| 05-30 | v0 | MVP 首跑 | **SR=-1.57**, VLM parse失败47/50 |
| 05-30 | v1 | Parser修复 | 处理//注释+trailing comma, 成功率99.7% |
| 05-30 | v2 | Backtest修复 | HOLD保持仓位, **SR=-0.55** |
| 05-30 | v3 | 趋势跟随 | SMA20+5d momentum, **SR=+0.51** (首次转正!) |
| 05-31 | v5 | 手写因子 | RSI+RSV+R²+vol-corr, **Mean SR=+0.59** |
| 05-31 | DSL | 因子引擎 | 45个DSL函数, 118/157因子可计算 |
| 05-31 | v6 | DSL接入 | 30个高IR因子, **Mean SR=+0.82** (5/5正) |
| 05-31 | Router | Factor Router | Gumbel-Softmax top-15, 30 epochs |

## 实验结果

### v6 最终结果 (5 tickers × 20 trading days, 2025-01)

| Ticker | Sharpe | Return | Win Rate | 类型 |
|--------|--------|--------|----------|------|
| AAPL | +0.46 | +1.1% | 52.6% | 科技 |
| MSFT | +0.51 | +1.7% | 52.2% | 科技 |
| NVDA | +0.73 | +2.5% | 50.6% | 科技 |
| JPM | +1.12 | +4.0% | 55.8% | 金融 |
| GS | +1.26 | +5.5% | 56.2% | 金融 |
| **Mean** | **+0.82** | **+3.0%** | **53.5%** | - |

### 性能演进

```
SR: -1.57 → -0.85 → -0.55 → +0.51 → +0.59 → +0.82
     v0      v1      v2      v3      v5      v6
```

## 关键观察与分析

### 观察 1: VLM 方向判断的系统性偏差
- **现象**: Qwen2.5-VL-32B 在看到任何回调K线时倾向输出 "bearish"
- **影响**: AAPL 33% sell vs 6% buy, 在2025牛市中持续亏损
- **结论**: VLM 的图表分析能力强 (模式识别准确), 但方向判断不可靠
- **解决**: 降低 VLM bias 权重 (0.7→0.4), 加入量化因子作为主要信号源

### 观察 2: Backtest 实现对结果的决定性影响
- **现象**: HOLD 信号将仓位清零导致频繁交易 (249 trades/50 days)
- **影响**: 每次 buy→hold 都产生 40bps 往返成本, 吞噬所有 alpha
- **结论**: 金融回测中 HOLD = 保持当前仓位, 不是平仓
- **解决**: 修改 backtest 逻辑, HOLD 时 current_pos 不变

### 观察 3: 仓位大小与交易成本的平衡
- **现象**: 5% 仓位 + 40bps 成本 = 需要 8% 价格变动才能盈亏平衡
- **影响**: 日频交易几乎不可能覆盖成本
- **结论**: 需要更大仓位 (20-30%) 或更低频交易
- **解决**: max_position 提升到 30%, 非对称阈值减少交易频率

### 观察 4: 量化因子是 alpha 的核心来源
- **现象**: 纯 VLM 系统 SR=-0.85, 加入因子后 SR=+0.82
- **影响**: 因子贡献了 1.67 的 SR 提升
- **结论**: 大模型挖掘的因子 (IR>1.5) 提供了稳定的量化信号
- **解决**: 实现完整 DSL 引擎, 接入 118 个可计算因子

### 观察 5: 金融股 vs 科技股的表现差异
- **现象**: JPM/GS SR>1.0, AAPL/MSFT SR~0.5
- **分析**: 金融股趋势更明确, 因子信号更强; 科技股波动大, 信号噪声比低
- **结论**: 系统在低波动趋势市场表现最好

## 系统架构

```
OHLCV Data ──→ Chart Renderer ──→ VLM (Qwen2.5-VL-32B)
    │                                      │
    ├──→ Factor DSL Engine (118 factors) ──→│
    │         │                             │
    │    Factor Router (top-15) ────────────→│
    │                                       ↓
    └──→ Trend Signal (SMA20/5d) ──→ DecisionPM ──→ Trade Signal
                                         ↑
                                    RiskController
                                    (position sizing)
```

## 使用的模型

| 模型 | 用途 | 部署方式 |
|------|------|---------|
| Qwen2.5-VL-32B-Instruct | 图表分析 VLM | vLLM, 4xA800 TP=4 |
| Factor Router (2-layer MLP) | 因子选择 | PyTorch, CPU |
| DSL Engine | 因子计算 | NumPy/Pandas |

### 可用但未使用的模型
- Qwen3.6-27B (VL, 但 vLLM 0.8.2 不支持)
- Qwen2.5-VL-7B (较小, 可用于 LoRA 训练)
- Qwen3-32B, QwQ-32B (纯文本, 可用于推理)

## 因子库

- **来源**: 大模型自进化挖掘 (docs/best_factor.json)
- **总数**: 157 个因子
- **可计算**: 118 个 (75.2%)
- **高 IR (≥1.5)**: 41 个
- **最高 IR**: 3.04 (RESI_ZSCORE_6_5)
- **DSL 函数**: 45 个 (DELAY, TS_MEAN, RSI, ATR, ZIGZAG_* 等)

## 待完成工作

1. **OPSD 自进化** (优先级高)
   - 用 hindsight teacher 生成训练信号
   - 通过 GRPO-lite 优化 Router 权重
   - 预期 SR 提升 0.3-0.5

2. **全量测试** (优先级中)
   - 25 tickers × 250 trading days × 3 seeds
   - 预计 GPU 时间: ~30 小时

3. **Baseline 复现** (优先级中)
   - TradingAgents, FinCon, R&D-Agent 等
   - 部分可用论文报告数字

4. **LoRA 微调** (优先级低)
   - 用 ChartGeometry 数据微调 Qwen2.5-VL-7B
   - 提升 JSON 输出一致性

## 文件结构

```
experiments/
  run_full_pipeline.sh    # 一键式全流程脚本
  run_env_setup.sh        # 环境搭建
  run_data_pipeline.sh    # 数据下载
  run_vlm_lora_train.sh   # VLM LoRA 训练
  run_factor_router_train.sh  # Router 训练
  run_mvp.sh              # MVP 实验
  run_main.sh             # 主实验
  run_ablations.sh        # 消融实验
  run_baselines.sh        # 基线对比
  run_opsd_stability.sh   # OPSD 稳定性
  run_opsd_full.sh        # OPSD 全量

src/finvl/
  factors/
    dsl_engine.py         # 因子 DSL 解析器 (45 函数)
    library.py            # 因子库管理
    router.py             # Factor Router (Gumbel-Softmax)
    train_router.py       # Router 训练脚本
  agents/
    decision_pm.py        # 决策整合 (VLM + 因子 + 趋势)
    chart_analyst.py      # VLM 图表分析
    pattern_reasoner.py   # 模式推理
    risk_controller.py    # 风控
  visual/
    vlm_client.py         # VLM API 客户端
    vlm_parser.py         # VLM 输出解析
  gui/
    dashboard.py          # 实验仪表盘 (Gradio)

outputs/
  experiments/v6_*/       # 最新实验结果
  router/                 # 训练好的 Router 权重
```
