"""
FinVL-MAS Interactive Dashboard
Gradio-based GUI for chart analysis, agent reasoning visualization,
and experiment result exploration.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

try:
    import gradio as gr
except ImportError:
    raise ImportError("Install gradio: pip install gradio>=4.0")

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
except ImportError:
    raise ImportError("Install plotly: pip install plotly")

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from finvl.core.types import Action, ChartGeometry, DecisionOutput
from finvl.visual.geometry import GeometryExtractor
from finvl.visual.candlestick import CandlestickClassifier
from finvl.visual.formations import FormationDetector
from finvl.evaluation.metrics import compute_all_metrics

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Plotly chart rendering
# ──────────────────────────────────────────────

def render_interactive_chart(df: pd.DataFrame, geometry: ChartGeometry | None = None,
                              title: str = "Chart") -> go.Figure:
    """Render an interactive Plotly candlestick chart with geometry overlays."""
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03,
        row_heights=[0.75, 0.25],
        subplot_titles=[title, "Volume"],
    )

    fig.add_trace(go.Candlestick(
        x=df.index, open=df["open"], high=df["high"],
        low=df["low"], close=df["close"], name="OHLC",
        increasing_line_color="#26a69a", decreasing_line_color="#ef5350",
    ), row=1, col=1)

    colors = ["#26a69a" if c >= o else "#ef5350"
              for o, c in zip(df["open"], df["close"])]
    fig.add_trace(go.Bar(
        x=df.index, y=df["volume"], name="Volume",
        marker_color=colors, opacity=0.5,
    ), row=2, col=1)

    # Add SMA overlays
    if len(df) >= 20:
        sma20 = df["close"].rolling(20).mean()
        fig.add_trace(go.Scatter(
            x=df.index, y=sma20, name="SMA20",
            line=dict(color="#ff9800", width=1),
        ), row=1, col=1)
    if len(df) >= 5:
        sma5 = df["close"].rolling(5).mean()
        fig.add_trace(go.Scatter(
            x=df.index, y=sma5, name="SMA5",
            line=dict(color="#2196f3", width=1),
        ), row=1, col=1)

    # Draw geometry overlays
    if geometry:
        for tl in geometry.trendlines:
            x0, x1 = tl.start_idx, tl.end_idx
            if 0 <= x0 < len(df) and 0 <= x1 < len(df):
                y0 = tl.slope * x0 + tl.intercept
                y1 = tl.slope * x1 + tl.intercept
                color = "#4caf50" if tl.direction.value == "up" else "#f44336"
                fig.add_shape(type="line",
                    x0=df.index[x0], y0=y0, x1=df.index[x1], y1=y1,
                    line=dict(color=color, width=2, dash="dash"),
                    row=1, col=1)

        for sr in geometry.support_resistance:
            color = "#2196f3" if sr.level_type == "support" else "#ff5722"
            fig.add_hline(y=sr.price, line_dash="dot",
                          line_color=color, opacity=0.6,
                          annotation_text=f"{sr.level_type} {sr.price:.2f}",
                          row=1, col=1)

    fig.update_layout(
        template="plotly_dark",
        height=600,
        xaxis_rangeslider_visible=False,
        showlegend=True,
        margin=dict(l=50, r=30, t=50, b=30),
        font=dict(family="Inter, sans-serif", size=12),
    )
    return fig


def render_agent_flow_diagram(outputs: list[Dict[str, Any]]) -> str:
    """Render a Mermaid-compatible agent flow diagram as HTML."""
    rows = []
    for o in outputs:
        status = "✅" if o.get("success", True) else "❌"
        conf = o.get("confidence", 0)
        name = o.get("agent_name", "?")
        bar_width = int(conf * 100)
        color = "#4caf50" if conf > 0.6 else "#ff9800" if conf > 0.3 else "#f44336"
        rows.append(f"""
        <div style="margin:8px 0; display:flex; align-items:center; gap:12px;">
            <span style="width:160px; font-weight:600;">{status} {name}</span>
            <div style="flex:1; background:#333; border-radius:4px; height:20px; position:relative;">
                <div style="width:{bar_width}%; background:{color}; height:100%;
                            border-radius:4px; transition:width 0.3s;"></div>
            </div>
            <span style="width:50px; text-align:right; font-size:13px;">{conf:.0%}</span>
        </div>""")
    return f"""<div style="padding:16px; background:#1e1e1e; border-radius:8px;
                color:#eee; font-family:Inter,sans-serif;">
        <h3 style="margin:0 0 12px 0;">Agent Pipeline Results</h3>
        {"".join(rows)}
    </div>"""


# ──────────────────────────────────────────────
# Core analysis function
# ──────────────────────────────────────────────

def analyze_csv(file_obj, lookback: int, asset_name: str):
    """Main analysis entry point for the GUI."""
    if file_obj is None:
        return None, "No file uploaded", "<p>Upload a CSV first</p>", "{}"

    df = pd.read_csv(file_obj.name, parse_dates=True, index_col=0)
    # Normalize columns
    col_map = {c: c.lower() for c in df.columns}
    df = df.rename(columns=col_map)
    for required in ["open", "high", "low", "close", "volume"]:
        if required not in df.columns:
            return None, f"Missing column: {required}", "", "{}"

    df = df.sort_index().tail(lookback)

    # Extract geometry
    extractor = GeometryExtractor()
    geometry = extractor.extract(df)

    classifier = CandlestickClassifier()
    extra_patterns = classifier.classify(df)
    geometry.candlestick_patterns.extend(extra_patterns)

    detector = FormationDetector()
    extra_formations = detector.detect(df)
    geometry.formations.extend(extra_formations)

    # Render chart
    chart_fig = render_interactive_chart(df, geometry, title=asset_name or "Analysis")

    # Build summary
    summary_lines = [
        f"**Asset:** {asset_name or 'Unknown'}",
        f"**Period:** {df.index[0]} to {df.index[-1]} ({len(df)} bars)",
        f"**Current Price:** {df['close'].iloc[-1]:.2f}",
        f"**Regime:** {geometry.regime.regime.value}",
        f"**Bias:** {geometry.overall_bias.value}",
        f"**Confidence:** {geometry.confidence:.2f}",
        "",
        f"**Trendlines:** {len(geometry.trendlines)}",
        f"**S/R Levels:** {len(geometry.support_resistance)}",
        f"**Candlestick Patterns:** {len(geometry.candlestick_patterns)}",
        f"**Formations:** {len(geometry.formations)}",
        f"**Volume Signals:** {len(geometry.volume_signals)}",
    ]
    summary = "\n".join(summary_lines)

    # Simulate agent pipeline outputs for visualization
    agent_outputs = [
        {"agent_name": "ChartAnalyst", "success": True, "confidence": geometry.confidence},
        {"agent_name": "PatternReasoner", "success": True,
         "confidence": 0.6 if geometry.formations else 0.3},
        {"agent_name": "EventAnalyst", "success": True, "confidence": 0.1},
        {"agent_name": "RiskController", "success": True,
         "confidence": 0.7 if geometry.regime.volatility_percentile < 0.7 else 0.4},
        {"agent_name": "DecisionPM", "success": True,
         "confidence": geometry.confidence * 0.8},
    ]
    agent_html = render_agent_flow_diagram(agent_outputs)

    # Build geometry JSON
    geo_dict = {
        "trendlines": [{"direction": t.direction.value, "slope": round(t.slope, 4),
                         "r2": round(t.r_squared, 3), "confidence": round(t.confidence, 2)}
                        for t in geometry.trendlines],
        "support_resistance": [{"price": round(s.price, 2), "type": s.level_type,
                                 "strength": round(s.strength, 2), "touches": s.touch_count}
                                for s in geometry.support_resistance],
        "candlestick_patterns": [{"pattern": p.pattern, "implication": p.implication.value}
                                  for p in geometry.candlestick_patterns[:10]],
        "formations": [{"type": f.formation_type, "stage": f.stage.value,
                         "confidence": round(f.confidence, 2)}
                        for f in geometry.formations],
        "regime": {"state": geometry.regime.regime.value,
                   "trend_strength": round(geometry.regime.trend_strength, 4),
                   "volatility": round(geometry.regime.volatility_percentile, 2)},
        "bias": geometry.overall_bias.value,
    }
    geo_json = json.dumps(geo_dict, indent=2)

    return chart_fig, summary, agent_html, geo_json


def load_experiment_results(results_dir: str):
    """Load and display experiment results from a directory."""
    p = Path(results_dir)
    if not p.exists():
        return "<p>Directory not found</p>", "{}"

    metrics_path = p / "metrics.json"
    if metrics_path.exists():
        with open(metrics_path) as f:
            metrics = json.load(f)
    else:
        return "<p>No metrics.json found</p>", "{}"

    # Build metrics dashboard HTML
    cards = []
    key_metrics = [
        ("Sharpe Ratio", "sharpe_ratio", "#4caf50"),
        ("Ann. Return", "annualized_return", "#2196f3"),
        ("Max Drawdown", "max_drawdown", "#f44336"),
        ("Win Rate", "win_rate", "#ff9800"),
        ("Dir. Accuracy", "directional_accuracy", "#9c27b0"),
        ("Total Return", "total_return", "#00bcd4"),
    ]
    for label, key, color in key_metrics:
        val = metrics.get(key, 0)
        fmt = f"{val:.2%}" if "rate" in key or "return" in key or "accuracy" in key or "drawdown" in key else f"{val:.4f}"
        cards.append(f"""
        <div style="background:#2a2a2a; border-radius:12px; padding:20px; text-align:center;
                    border-left:4px solid {color}; min-width:140px;">
            <div style="color:#999; font-size:12px; text-transform:uppercase; letter-spacing:1px;">{label}</div>
            <div style="color:{color}; font-size:28px; font-weight:700; margin-top:8px;">{fmt}</div>
        </div>""")

    html = f"""<div style="display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr));
                gap:16px; padding:16px; background:#1a1a1a; border-radius:16px;">
        {"".join(cards)}
    </div>"""

    return html, json.dumps(metrics, indent=2)


# ──────────────────────────────────────────────
# Gradio App
# ──────────────────────────────────────────────

def create_app() -> gr.Blocks:
    """Create the Gradio Blocks app."""

    custom_css = """
    .gradio-container { max-width: 1400px !important; }
    .tab-nav button { font-size: 15px !important; font-weight: 600 !important; }
    """

    with gr.Blocks(
        title="FinVL-MAS Dashboard",
        theme=gr.themes.Soft(
            primary_hue="teal",
            secondary_hue="orange",
            neutral_hue="gray",
            font=gr.themes.GoogleFont("Inter"),
        ),
        css=custom_css,
    ) as app:
        gr.Markdown("""
        # 📊 FinVL-MAS — Visual Trader Cognition Dashboard
        **Structured Visual Reasoning over Chart Geometry for Financial Decision Making**

        Upload OHLCV data to analyze chart geometry, run the multi-agent reasoning pipeline,
        and explore experiment results interactively.
        """)

        with gr.Tabs():
            # ── Tab 1: Chart Analysis ──
            with gr.Tab("🔍 Chart Analysis", id="analysis"):
                with gr.Row():
                    with gr.Column(scale=1):
                        file_input = gr.File(label="Upload OHLCV CSV", file_types=[".csv"])
                        asset_input = gr.Textbox(label="Asset Name", value="ASSET", max_lines=1)
                        lookback_input = gr.Slider(20, 250, value=60, step=10, label="Lookback Window (bars)")
                        analyze_btn = gr.Button("Analyze Chart", variant="primary", size="lg")
                    with gr.Column(scale=3):
                        chart_output = gr.Plot(label="Interactive Chart")

                with gr.Row():
                    with gr.Column(scale=1):
                        summary_output = gr.Markdown(label="Analysis Summary")
                    with gr.Column(scale=1):
                        agent_html = gr.HTML(label="Agent Pipeline")
                    with gr.Column(scale=1):
                        geo_json_output = gr.Code(label="Chart Geometry (JSON)", language="json")

                analyze_btn.click(
                    fn=analyze_csv,
                    inputs=[file_input, lookback_input, asset_input],
                    outputs=[chart_output, summary_output, agent_html, geo_json_output],
                )

            # ── Tab 2: Experiment Results ──
            with gr.Tab("📈 Experiment Results", id="results"):
                results_dir_input = gr.Textbox(
                    label="Experiment Output Directory",
                    value="outputs/experiments/",
                    max_lines=1,
                )
                load_btn = gr.Button("Load Results", variant="primary")
                results_html = gr.HTML(label="Metrics Dashboard")
                results_json = gr.Code(label="Full Metrics (JSON)", language="json")

                load_btn.click(
                    fn=load_experiment_results,
                    inputs=[results_dir_input],
                    outputs=[results_html, results_json],
                )

            # ── Tab 3: About ──
            with gr.Tab("ℹ️ About", id="about"):
                gr.Markdown("""
                ## FinVL-MAS: Structured Visual Reasoning for Financial Decision Making

                ### System Architecture
                The system decomposes expert trader cognition into five specialist agents:

                | Agent | Role | Key Outputs |
                |-------|------|-------------|
                | **ChartAnalyst** | Perceive chart geometry | Trendlines, S/R, patterns |
                | **PatternReasoner** | Interpret formations | Directional hypothesis |
                | **EventAnalyst** | Integrate context | Event impact assessment |
                | **RiskController** | Assess risk | Position sizing, stop-loss |
                | **DecisionPM** | Final decision | Buy/Sell/Hold with rationale |

                ### How It Works
                1. **Render** financial data as candlestick charts
                2. **Extract** chart geometry (trendlines, support/resistance, patterns)
                3. **Route** through specialist agents via gated shared memory
                4. **Decide** with confidence-weighted evidence integration
                5. **Evaluate** under realistic backtesting conditions

                ### Citation
                ```bibtex
                @article{finvlmas2025,
                  title={FinVL-MAS: Structured Visual Reasoning over Chart Geometry
                         for Financial Decision Making},
                  year={2025}
                }
                ```
                """)

    return app


def main():
    app = create_app()
    app.launch(server_name="0.0.0.0", server_port=7860, share=False)


if __name__ == "__main__":
    main()
