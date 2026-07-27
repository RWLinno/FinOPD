"""
FinOPD Experiment Dashboard - 增强版可视化 GUI
展示实验进度、结果对比、因子分析、系统架构、实时监控
启动: cd /Knowin/foundation/weilinruan/FinOPD && python -m finvl.gui.dashboard
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

try:
    import gradio as gr
except ImportError:
    raise ImportError("pip install gradio>=4.0")

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
except ImportError:
    raise ImportError("pip install plotly>=5.0")

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


def load_experiment_log():
    return [
        {"date": "05-28 15:00", "stage": "S0", "event": "环境搭建", "detail": "4xA800 + PyTorch 2.10 + conda", "status": "✅"},
        {"date": "05-28 16:00", "stage": "S1", "event": "数据构建", "detail": "Dow-30 OHLCV 52775行 + ChartGeometry 2375样本", "status": "✅"},
        {"date": "KDD", "stage": "S2", "event": "vLLM 配置", "detail": "Qwen3.5-9B student / Qwen3.5-27B teacher", "status": "✅"},
        {"date": "05-30 20:20", "stage": "v0", "event": "MVP 首跑", "detail": "SR=-1.57, VLM parse失败47/50", "status": "❌"},
        {"date": "05-30 21:10", "stage": "v1", "event": "Parser修复", "detail": "处理//注释+trailing comma → 99.7%成功", "status": "✅"},
        {"date": "05-30 23:20", "stage": "v2", "event": "Backtest修复", "detail": "HOLD保持仓位 → SR: -1.57→-0.55", "status": "✅"},
        {"date": "05-31 11:25", "stage": "v3", "event": "趋势跟随+仓位", "detail": "SMA20+30%仓位 → SR=+0.51 首次转正!", "status": "✅"},
        {"date": "05-31 15:08", "stage": "v5", "event": "手写因子", "detail": "RSI+RSV+R²+vol-corr → Mean SR=+0.59", "status": "✅"},
        {"date": "05-31 16:45", "stage": "DSL", "event": "因子DSL引擎", "detail": "45函数, 118/157因子可计算 (75.2%)", "status": "✅"},
        {"date": "05-31 17:50", "stage": "v6", "event": "DSL因子接入", "detail": "30个高IR因子 → Mean SR=+0.82 (5/5正)", "status": "✅"},
        {"date": "05-31 16:50", "stage": "Router", "event": "Factor Router", "detail": "Gumbel-Softmax top-15, 30 epochs", "status": "✅"},
    ]


def create_sr_evolution():
    labels = ['原始\n(VLM only)', 'Parser\n修复', 'Backtest\n修复', '趋势跟随\n+仓位', '手写\n因子', 'DSL\n因子库']
    sr_values = [-0.85, -0.85, -0.55, 0.51, 0.59, 0.82]
    colors = ['#ef5350' if v < 0 else '#26a69a' for v in sr_values]

    fig = go.Figure()
    fig.add_trace(go.Bar(x=labels, y=sr_values, marker_color=colors,
                         text=[f'{v:.2f}' for v in sr_values], textposition='outside'))
    fig.add_hline(y=0, line_dash="dash", line_color="gray", line_width=2)
    fig.add_annotation(x='DSL\n因子库', y=0.82, text="当前最佳", showarrow=True, arrowhead=2, font=dict(size=12, color="green"))
    fig.update_layout(title="Sharpe Ratio 迭代演进", yaxis_title="Mean Sharpe Ratio",
                      template="plotly_white", height=420, margin=dict(t=50, b=80))
    return fig


def create_ticker_chart():
    tickers = ['AAPL', 'MSFT', 'NVDA', 'JPM', 'GS']
    srs = [0.4630, 0.5073, 0.7347, 1.1237, 1.2591]
    wrs = [52.6, 52.2, 50.6, 55.8, 56.2]
    crs = [1.05, 1.66, 2.49, 3.97, 5.53]

    fig = make_subplots(rows=1, cols=3, subplot_titles=("Sharpe Ratio", "Win Rate (%)", "Cumulative Return (%)"))
    fig.add_trace(go.Bar(x=tickers, y=srs, marker_color=['#1976d2']*5, showlegend=False), row=1, col=1)
    fig.add_trace(go.Bar(x=tickers, y=wrs, marker_color=['#388e3c']*5, showlegend=False), row=1, col=2)
    fig.add_trace(go.Bar(x=tickers, y=crs, marker_color=['#f57c00']*5, showlegend=False), row=1, col=3)
    fig.add_hline(y=0, line_dash="dash", line_color="gray", row=1, col=1)
    fig.add_hline(y=50, line_dash="dash", line_color="gray", row=1, col=2)
    fig.update_layout(title="v6 Per-Ticker Performance (20 trading days, Jan 2025)",
                      template="plotly_white", height=350)
    return fig


def create_factor_ir_chart():
    factor_path = PROJECT_ROOT / "docs" / "best_factor.json"
    irs = []
    if factor_path.exists():
        with open(factor_path) as f:
            for line in f:
                line = line.strip()
                if not line or line == 'null':
                    continue
                try:
                    d = json.loads(line)
                    if d and 'Information_Ratio_with_cost' in d:
                        irs.append(d['Information_Ratio_with_cost'])
                except (json.JSONDecodeError, TypeError, ValueError):
                    pass

    fig = go.Figure()
    fig.add_trace(go.Histogram(x=irs, nbinsx=25, marker_color='#7b1fa2', opacity=0.8))
    fig.add_vline(x=1.0, line_dash="dash", line_color="red", annotation_text="IR=1.0")
    fig.add_vline(x=2.0, line_dash="dash", line_color="orange", annotation_text="IR=2.0")
    fig.update_layout(title=f"因子 Information Ratio 分布 ({len(irs)} factors)",
                      xaxis_title="IR (with cost)", yaxis_title="Count",
                      template="plotly_white", height=350)
    return fig


def create_decision_flow_chart():
    fig = go.Figure()
    # Sankey diagram showing decision flow
    fig.add_trace(go.Sankey(
        node=dict(
            pad=15, thickness=20,
            label=["OHLCV", "Chart Image", "VLM Analysis", "Factor DSL\n(118 factors)",
                   "Factor Router\n(top-15)", "Trend Signal", "DecisionPM",
                   "BUY", "HOLD", "SELL"],
            color=["#42a5f5", "#66bb6a", "#ab47bc", "#ff7043",
                   "#26c6da", "#ffa726", "#ec407a",
                   "#4caf50", "#9e9e9e", "#f44336"]
        ),
        link=dict(
            source=[0, 0, 1, 2, 3, 4, 5, 6, 6, 6],
            target=[1, 3, 2, 6, 4, 6, 6, 7, 8, 9],
            value=[10, 10, 10, 4, 8, 6, 7, 3, 5, 2],
        )
    ))
    fig.update_layout(title="决策流程 (Data Flow)", template="plotly_white", height=400)
    return fig


def refresh_results():
    """Refresh results from latest pipeline run."""
    results_dir = PROJECT_ROOT / "outputs" / "experiments" / "pipeline_quick"
    if not results_dir.exists():
        return "暂无 pipeline_quick 结果，请先运行实验"

    lines = []
    for ticker_dir in sorted(results_dir.iterdir()):
        if ticker_dir.is_dir() and ticker_dir.name != "summary.json":
            for sub in ticker_dir.iterdir():
                mf = sub / "metrics.json"
                if mf.exists():
                    m = json.loads(mf.read_text())
                    lines.append(f"**{ticker_dir.name}**: SR={m.get('sharpe_ratio',0):.4f}, "
                                 f"WR={m.get('win_rate',0):.1%}, "
                                 f"CR={m.get('total_return',0):.2%}, "
                                 f"MDD={m.get('max_drawdown',0):.2%}")
    if not lines:
        return "实验正在运行中..."
    return "\n\n".join(lines)


def build_app():
    with gr.Blocks(title="FinOPD Experiment Dashboard") as app:
        gr.Markdown("# 🏦 FinOPD 实验仪表盘")
        gr.Markdown("**On-Policy Distillation for Financial Portfolio Decision** | Qwen3.5-9B Student + Qwen3.5-27B Teacher + 157 Frozen Factors")

        with gr.Tabs():
            with gr.Tab("📊 实验总览"):
                with gr.Row():
                    with gr.Column(scale=2):
                        gr.Plot(create_sr_evolution())
                    with gr.Column(scale=1):
                        gr.Markdown("""
### 关键指标
| 指标 | 值 |
|------|-----|
| Mean SR | **+0.82** |
| Win Rate | **53.5%** |
| Positive Tickers | **5/5** |
| VLM Parse Rate | **99.7%** |
| Factors Used | **30/118** |
| Router top-k | **15** |
""")
                gr.Plot(create_ticker_chart())

            with gr.Tab("📅 实验时间线"):
                log = load_experiment_log()
                df = pd.DataFrame(log)
                gr.Dataframe(df, label="实验执行日志 (2026-05-28 ~ 2026-05-31)")

            with gr.Tab("🔬 因子分析"):
                gr.Plot(create_factor_ir_chart())
                gr.Markdown("""
### 因子库统计
| 指标 | 值 |
|------|-----|
| 总因子数 | 157 (大模型自进化挖掘) |
| 可计算因子 | 118 (75.2%) |
| 高 IR (≥1.5) | 41 个 |
| 最高 IR | 3.04 (RESI_ZSCORE_6_5) |
| DSL 函数 | 45 个 |
| Top-5 因子 | RESI_ZSCORE_6_5 (3.04), QTLD5_RSI_Delta (2.93), QTLU5_TREND (2.79), MEAN_DEV_RANK (2.75), RSV3_TS_ZSCORE (2.73) |
""")

            with gr.Tab("🏗️ 系统架构"):
                gr.Plot(create_decision_flow_chart())
                gr.Markdown("""
### 模型与组件

| 组件 | 实现 | 状态 |
|------|------|------|
| Deployable student | Qwen3.5-9B | ✅ configured |
| Frozen hindsight teacher | Qwen3.5-27B | ✅ training only |
| Factor DSL | 45 函数引擎 | ✅ 118/157 可计算 |
| Factor Router | Gumbel-Softmax MLP | ✅ 30 epochs trained |
| DecisionPM | Weighted fusion | ✅ VLM+Factor+Trend |
| Backtest | Vectorized + costs | ✅ 15bps+5bps+1d delay |
| OPSD | Self-distillation | ⏳ 脚本就绪 |

### 可用模型列表
- **Qwen3.5-9B**（视觉几何、student 与部署决策）
- **Qwen3.5-27B**（冻结 hindsight teacher，仅训练期）
""")

            with gr.Tab("📈 实时结果"):
                gr.Markdown("### Pipeline Quick 运行结果")
                result_display = gr.Markdown(refresh_results())
                refresh_btn = gr.Button("🔄 刷新结果")
                refresh_btn.click(fn=refresh_results, outputs=result_display)

            with gr.Tab("💡 关键发现"):
                gr.Markdown("""
### 实验关键发现与结论

#### 发现 1: VLM 方向判断需要量化因子校正
- **观察**: VLM 对短期回调过度敏感, 频繁输出 bearish (AAPL: 33% sell vs 6% buy)
- **分析**: 视觉模型擅长模式识别但缺乏统计基础, 容易被噪声干扰
- **结论**: VLM bias 权重应降低 (0.7→0.4), 量化因子作为主信号源
- **效果**: SR 从 -0.85 提升到 +0.82

#### 发现 2: Backtest 实现细节是 alpha 的隐形杀手
- **观察**: HOLD=清零仓位导致 249 trades/50 days, 交易成本吞噬所有收益
- **分析**: 金融回测中 HOLD 应保持当前仓位, 只有 BUY/SELL 改变持仓
- **结论**: 回测逻辑的正确性比模型复杂度更重要
- **效果**: 单项修复贡献 SR +0.3

#### 发现 3: 仓位大小决定能否覆盖交易成本
- **观察**: 5% 仓位 + 40bps 往返成本 = 需要 8% 价格变动才能盈亏平衡
- **分析**: 日频交易中, 小仓位几乎不可能覆盖成本
- **结论**: 高 conviction 时使用 20-30% 仓位, 非对称阈值减少交易频率
- **效果**: SR 从 -0.55 跳升到 +0.51

#### 发现 4: 大模型挖掘的因子是真正的 alpha 来源
- **观察**: 118 个可计算因子中, 41 个 IR>1.5, 最高 3.04
- **分析**: 因子共识信号 (positive fraction) 比单一因子更稳健
- **结论**: DSL 引擎 + Factor Router 是系统的核心竞争力
- **效果**: 接入因子后 AAPL 从 -0.65 翻正到 +0.46

#### 发现 5: 金融股 vs 科技股的 regime 差异
- **观察**: JPM SR=1.12, GS SR=1.26 vs AAPL SR=0.46, NVDA SR=0.73
- **分析**: 金融股趋势更明确, 因子信号噪声比更高; 科技股波动大
- **结论**: Factor Router 的 regime 适应性是提升科技股表现的关键
""")

    return app


if __name__ == "__main__":
    app = build_app()
    app.launch(server_name="0.0.0.0", server_port=14075, share=True)
