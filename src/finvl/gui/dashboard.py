"""
FinOPD Experiment Dashboard - 增强版可视化 GUI
展示实验进度、结果对比、因子分析、系统架构、实时监控
启动: cd /mnt/nas/weilinruan/FinOPD && python -m finvl.gui.dashboard
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
except ImportError:
    raise ImportError("pip install plotly>=5.0")

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


def load_experiment_log():
    return [
        {"date": "KDD", "stage": "Factors", "event": "Binary artifact audit", "detail": "157/157 finite; source manifest not exposed", "status": "✅"},
        {"date": "KDD", "stage": "Router", "event": "Recorded-mask routing", "detail": "ordered checkpoint; deterministic top-15", "status": "✅"},
        {"date": "KDD", "stage": "Memory", "event": "Availability filter", "detail": "future outcomes excluded before similarity search", "status": "✅"},
        {"date": "KDD", "stage": "OPSD", "event": "Dual-model smoke", "detail": "Qwen3.5-9B update + frozen Qwen3.5-27B teacher", "status": "✅"},
        {"date": "KDD", "stage": "Finance", "event": "Locked factorial matrix", "detail": "0/27 auditable arm/seed runs available", "status": "⏳"},
    ]


def create_sr_evolution():
    labels = ["Factor artifact", "Router", "Time-safe memory", "9B/27B smoke"]
    passed = [1, 1, 1, 1]

    fig = go.Figure()
    fig.add_trace(go.Bar(x=labels, y=passed, marker_color="#26a69a",
                         text=["PASS"] * len(labels), textposition="inside"))
    fig.update_layout(title="可复核组件审计（不代表金融收益）", yaxis_title="Audit pass",
                      yaxis=dict(range=[0, 1.15], tickvals=[0, 1]),
                      template="plotly_white", height=420, margin=dict(t=50, b=80))
    return fig


def create_ticker_chart():
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=["Expected arm/seed runs", "Complete", "Missing"],
        y=[27, 0, 27],
        marker_color=["#1976d2", "#26a69a", "#ef5350"],
        text=["27", "0", "27"],
        textposition="outside",
    ))
    fig.update_layout(title="锁定金融实验矩阵状态", yaxis_title="Runs",
                      template="plotly_white", height=350)
    return fig


def create_factor_ir_chart():
    from finvl.factors.library import FactorLibrary

    library = FactorLibrary(str(PROJECT_ROOT / "src/finvl/factors/frozen_factors.bin"))
    irs = [factor.ir for factor in library.factors.values() if factor.category == "evolved"]

    fig = go.Figure()
    fig.add_trace(go.Histogram(x=irs, nbinsx=25, marker_color='#7b1fa2', opacity=0.8))
    fig.add_vline(x=1.0, line_dash="dash", line_color="red", annotation_text="IR=1.0")
    fig.add_vline(x=2.0, line_dash="dash", line_color="orange", annotation_text="IR=2.0")
    fig.update_layout(title=f"冻结因子开发元数据（非 KDD 金融结果，{len(irs)} factors）",
                      xaxis_title="IR (with cost)", yaxis_title="Count",
                      template="plotly_white", height=350)
    return fig


def create_decision_flow_chart():
    fig = go.Figure()
    fig.add_trace(go.Sankey(
        node=dict(
            pad=15, thickness=20,
            label=["Point-in-time OHLCV/events", "4 structured specialists",
                   "157-factor binary", "Factor Router\n(top-15)",
                   "Eligible episodic memory", "Qwen3.5-9B policy",
                   "BUY / HOLD / SELL", "Matured outcome scalars",
                   "Frozen Qwen3.5-27B", "OPSD update"],
            color=["#42a5f5", "#66bb6a", "#ff7043", "#26c6da",
                   "#ffa726", "#ec407a", "#4caf50", "#9e9e9e",
                   "#7e57c2", "#5c6bc0"]
        ),
        link=dict(
            source=[0, 0, 2, 3, 1, 4, 5, 6, 7, 8],
            target=[1, 3, 3, 5, 5, 5, 6, 7, 8, 9],
            value=[10, 6, 6, 6, 10, 4, 10, 8, 8, 8],
        )
    ))
    fig.update_layout(title="部署与 post-horizon 更新的数据边界", template="plotly_white", height=400)
    return fig


def refresh_results():
    """Report only the fail-closed KDD factorial status."""
    status_path = PROJECT_ROOT / "outputs" / "kdd_factorial" / "factorial_status.json"
    if not status_path.is_file():
        return "未找到锁定实验状态；当前不能报告金融结果。"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    summary = status.get("summary", {})
    return (
        f"**Expected:** {summary.get('expected_runs', 'unknown')}  \n"
        f"**Missing:** {summary.get('missing_runs', 'unknown')}  \n"
        f"**Proxy results used:** {summary.get('proxy_results_used', 'unknown')}"
    )


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
### 当前证据边界
| 项目 | 状态 |
|------|------|
| 157 因子二进制审计 | **PASS** |
| Router deterministic top-k | **15** |
| Future-memory exclusion | **PASS** |
| Qwen3.5 9B/27B smoke | **PASS** |
| 金融 arm/seed runs | **0/27** |
| 金融优越性结论 | **WITHHELD** |
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
| 冻结记录 | 157 |
| 审计切片有限输出 | 157/157 |
| 审计切片非恒定输出 | 121/157 |
| 路由选择 | deterministic top-15 |
| 发布形式 | content-addressed binary only |
""")

            with gr.Tab("🏗️ 系统架构"):
                gr.Plot(create_decision_flow_chart())
                gr.Markdown("""
### 模型与组件

| 组件 | 实现 | 状态 |
|------|------|------|
| Deployable student | Qwen3.5-9B | ✅ configured |
| Frozen hindsight teacher | Qwen3.5-27B | ✅ training only |
| Structured specialists | Deterministic typed evidence | ✅ no trainable tokens |
| Factor artifact | 157 frozen expressions | ✅ binary only |
| Factor Router | factor-state MLP | ✅ recorded top-15 mask |
| DecisionPM | bounded JSON policy | ✅ 9B only |
| Portfolio evaluator | synchronized PnL | ✅ fail closed |
| Financial factorial | 9 arms × 3 seeds | ⏳ 27 runs missing |

### 可用模型列表
- **Qwen3.5-9B**（唯一 token student 与部署决策）
- **Qwen3.5-27B**（冻结 hindsight teacher，仅训练期）
""")

            with gr.Tab("📈 实时结果"):
                gr.Markdown("### KDD fail-closed factorial 状态")
                result_display = gr.Markdown(refresh_results())
                refresh_btn = gr.Button("🔄 刷新结果")
                refresh_btn.click(fn=refresh_results, outputs=result_display)

            with gr.Tab("💡 关键发现"):
                gr.Markdown("""
### 已验证结论

- 部署路径只有 Qwen3.5-9B 生成 token；Qwen3.5-27B 只在 horizon 闭合后提供冻结教师分布。
- 157 个因子保留在带内容哈希的二进制工件中；运行时不会暴露源 JSON 清单。
- Router 使用当前 157 因子状态并复用 rollout 记录的 deterministic top-15 mask。
- Episodic memory 在相似度搜索前按 `available_date` 排除未来结果。
- 双模型 smoke test 验证了 JSON 生成、同 completion 蒸馏、有限 JSD/KL 和一步更新。

### 尚不能声称

- 27 个锁定 arm/seed 运行目前均缺失，因此没有同步 Qwen3.5 portfolio PnL、置信区间或正向金融结论。
- 旧 Qwen2.5 原型的单资产或宏平均指标不能作为当前系统的实验结果。
""")

    return app


if __name__ == "__main__":
    app = build_app()
    app.launch(server_name="0.0.0.0", server_port=14075, share=True)
