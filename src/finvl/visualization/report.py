"""
HTML Experiment Report Generator for FinVL-MAS.
Produces a self-contained, interactive HTML report from experiment results
using Plotly for charts and modern CSS for layout.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


def _plotly_cdn() -> str:
    return '<script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>'


def _css() -> str:
    return """
    <style>
        :root { --bg: #0f1117; --card: #1a1b26; --border: #2a2b3d;
                --text: #c0caf5; --accent: #7aa2f7; --green: #9ece6a;
                --red: #f7768e; --orange: #e0af68; --purple: #bb9af7; }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { background: var(--bg); color: var(--text); font-family: 'Inter', 'Segoe UI', sans-serif;
               line-height: 1.6; padding: 24px; }
        .container { max-width: 1400px; margin: 0 auto; }
        h1 { color: var(--accent); font-size: 28px; margin-bottom: 8px; }
        h2 { color: var(--purple); font-size: 20px; margin: 32px 0 16px; border-bottom: 1px solid var(--border); padding-bottom: 8px; }
        h3 { color: var(--orange); font-size: 16px; margin: 20px 0 12px; }
        .subtitle { color: #565f89; font-size: 14px; margin-bottom: 24px; }
        .grid { display: grid; gap: 16px; }
        .grid-3 { grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); }
        .grid-2 { grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); }
        .card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 20px; }
        .metric-card { text-align: center; }
        .metric-label { font-size: 11px; text-transform: uppercase; letter-spacing: 1.5px; color: #565f89; }
        .metric-value { font-size: 32px; font-weight: 700; margin-top: 8px; }
        .metric-value.positive { color: var(--green); }
        .metric-value.negative { color: var(--red); }
        .metric-value.neutral { color: var(--accent); }
        table { width: 100%; border-collapse: collapse; font-size: 14px; }
        th { background: #1e1f2e; color: var(--accent); text-align: left; padding: 10px 12px;
             font-weight: 600; font-size: 12px; text-transform: uppercase; letter-spacing: 1px; }
        td { padding: 10px 12px; border-bottom: 1px solid var(--border); }
        tr:hover td { background: #1e1f2e; }
        .tag { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; }
        .tag-green { background: rgba(158,206,106,0.15); color: var(--green); }
        .tag-red { background: rgba(247,118,142,0.15); color: var(--red); }
        .tag-blue { background: rgba(122,162,247,0.15); color: var(--accent); }
        .chart-container { margin: 16px 0; }
        .footer { text-align: center; color: #565f89; font-size: 12px; margin-top: 40px; padding-top: 20px;
                  border-top: 1px solid var(--border); }
    </style>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
    """


def generate_report(
    metrics: Dict[str, float],
    ablation_results: Optional[Dict[str, Dict[str, float]]] = None,
    regime_results: Optional[Dict[str, Dict[str, float]]] = None,
    equity_curve: Optional[pd.Series] = None,
    decisions: Optional[List[Dict[str, Any]]] = None,
    config: Optional[Dict[str, Any]] = None,
    title: str = "FinVL-MAS Experiment Report",
    output_path: str = "outputs/report.html",
) -> str:
    """Generate a self-contained HTML experiment report."""
    parts = [
        "<!DOCTYPE html>",
        '<html lang="en"><head>',
        '<meta charset="UTF-8">',
        f"<title>{title}</title>",
        _plotly_cdn(),
        _css(),
        "</head><body>",
        '<div class="container">',
        f'<h1>📊 {title}</h1>',
        f'<div class="subtitle">Generated {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</div>',
    ]

    # ── Key Metrics Cards ──
    parts.append('<h2>Key Metrics</h2>')
    parts.append('<div class="grid grid-3">')
    card_defs = [
        ("Sharpe Ratio", "sharpe_ratio", "neutral", lambda v: f"{v:.4f}"),
        ("Ann. Return", "annualized_return", None, lambda v: f"{v:+.2%}"),
        ("Max Drawdown", "max_drawdown", None, lambda v: f"{v:.2%}"),
        ("Win Rate", "win_rate", None, lambda v: f"{v:.1%}"),
        ("Dir. Accuracy", "directional_accuracy", None, lambda v: f"{v:.1%}"),
        ("Total Return", "total_return", None, lambda v: f"{v:+.2%}"),
        ("Sharpe (no TC)", "sharpe_no_cost", "neutral", lambda v: f"{v:.4f}"),
        ("Calmar Ratio", "calmar_ratio", "neutral", lambda v: f"{v:.4f}"),
        ("Profit Factor", "profit_factor", "neutral", lambda v: f"{v:.2f}"),
    ]
    for label, key, force_class, fmt in card_defs:
        val = metrics.get(key, 0)
        if force_class:
            cls = force_class
        else:
            cls = "positive" if val > 0 else "negative" if val < 0 else "neutral"
        parts.append(f"""
        <div class="card metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value {cls}">{fmt(val)}</div>
        </div>""")
    parts.append("</div>")

    # ── Equity Curve ──
    if equity_curve is not None and len(equity_curve) > 0:
        parts.append('<h2>Equity Curve</h2>')
        parts.append('<div class="card"><div id="equity-chart" class="chart-container"></div></div>')
        dates_js = [d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)
                    for d in equity_curve.index]
        vals_js = [round(float(v), 2) for v in equity_curve.values]
        parts.append(f"""
        <script>
        Plotly.newPlot('equity-chart', [{{
            x: {json.dumps(dates_js)},
            y: {json.dumps(vals_js)},
            type: 'scatter', mode: 'lines',
            line: {{color: '#7aa2f7', width: 2}},
            fill: 'tozeroy', fillcolor: 'rgba(122,162,247,0.1)',
            name: 'Equity'
        }}], {{
            template: 'plotly_dark',
            paper_bgcolor: '#1a1b26', plot_bgcolor: '#1a1b26',
            margin: {{l:60, r:30, t:30, b:40}},
            yaxis: {{title: 'Portfolio Value', gridcolor: '#2a2b3d'}},
            xaxis: {{gridcolor: '#2a2b3d'}},
            font: {{family: 'Inter', color: '#c0caf5'}}
        }});
        </script>""")

    # ── Ablation Results Table ──
    if ablation_results:
        parts.append('<h2>Ablation Study</h2>')
        parts.append('<div class="card">')
        cols = ["sharpe_ratio", "annualized_return", "max_drawdown", "directional_accuracy", "win_rate"]
        parts.append("<table><thead><tr><th>Configuration</th>")
        for c in cols:
            parts.append(f"<th>{c.replace('_', ' ').title()}</th>")
        parts.append("</tr></thead><tbody>")
        for name, m in ablation_results.items():
            parts.append(f"<tr><td><strong>{name}</strong></td>")
            for c in cols:
                v = m.get(c, 0)
                if "return" in c or "drawdown" in c or "accuracy" in c or "rate" in c:
                    parts.append(f"<td>{v:.2%}</td>")
                else:
                    parts.append(f"<td>{v:.4f}</td>")
            parts.append("</tr>")
        parts.append("</tbody></table></div>")

        # Ablation bar chart
        parts.append('<div class="card"><div id="ablation-chart" class="chart-container"></div></div>')
        names = list(ablation_results.keys())
        sharpes = [ablation_results[n].get("sharpe_ratio", 0) for n in names]
        colors = ["#7aa2f7" if n.startswith("A1") else "#565f89" for n in names]
        parts.append(f"""
        <script>
        Plotly.newPlot('ablation-chart', [{{
            x: {json.dumps(names)},
            y: {json.dumps(sharpes)},
            type: 'bar',
            marker: {{color: {json.dumps(colors)}, line: {{width: 0}} }},
            text: {json.dumps([f"{s:.4f}" for s in sharpes])},
            textposition: 'outside',
            textfont: {{color: '#c0caf5', size: 12}}
        }}], {{
            template: 'plotly_dark',
            paper_bgcolor: '#1a1b26', plot_bgcolor: '#1a1b26',
            margin: {{l:60, r:30, t:40, b:80}},
            yaxis: {{title: 'Sharpe Ratio', gridcolor: '#2a2b3d'}},
            xaxis: {{tickangle: -30}},
            font: {{family: 'Inter', color: '#c0caf5'}},
            title: {{text: 'Ablation: Sharpe Ratio Comparison', font: {{size: 16}}}}
        }});
        </script>""")

    # ── Regime Analysis ──
    if regime_results:
        parts.append('<h2>Regime-Conditioned Analysis</h2>')
        parts.append('<div class="card"><div id="regime-chart" class="chart-container"></div></div>')
        regimes = list(regime_results.keys())
        full_sharpes = [regime_results[r].get("sharpe_ratio", 0) for r in regimes]
        parts.append(f"""
        <script>
        Plotly.newPlot('regime-chart', [{{
            x: {json.dumps(regimes)},
            y: {json.dumps(full_sharpes)},
            type: 'bar', name: 'Sharpe by Regime',
            marker: {{color: ['#9ece6a','#f7768e','#e0af68','#bb9af7','#7aa2f7']}}
        }}], {{
            template: 'plotly_dark',
            paper_bgcolor: '#1a1b26', plot_bgcolor: '#1a1b26',
            margin: {{l:60, r:30, t:40, b:60}},
            yaxis: {{title: 'Sharpe Ratio', gridcolor: '#2a2b3d'}},
            font: {{family: 'Inter', color: '#c0caf5'}},
            title: {{text: 'Performance by Market Regime', font: {{size: 16}}}}
        }});
        </script>""")

    # ── Config ──
    if config:
        parts.append('<h2>Experiment Configuration</h2>')
        parts.append(f'<div class="card"><pre style="color:#9ece6a; font-size:13px; overflow-x:auto;">{json.dumps(config, indent=2)}</pre></div>')

    # ── Footer ──
    parts.append(f"""
    <div class="footer">
        FinVL-MAS — Structured Visual Reasoning over Chart Geometry for Financial Decision Making<br>
        Report generated at {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    </div>""")

    parts.append("</div></body></html>")

    html = "\n".join(parts)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        f.write(html)
    return output_path
