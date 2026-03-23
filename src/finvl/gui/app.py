"""FinVL-MAS interactive GUI with research-demo oriented presentation."""

from __future__ import annotations

import asyncio
import dataclasses
import json
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

try:
    import gradio as gr
except ImportError as exc:
    raise ImportError("Install gradio: pip install gradio>=4.0") from exc

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
except ImportError as exc:
    raise ImportError("Install plotly: pip install plotly") from exc

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from finvl.core.config import load_config
from finvl.core.types import ChartGeometry
from finvl.visual.vlm_client import VLMClient, VLMRouter
from finvl.workflow.orchestrator import AgentOrchestrator

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parents[4]
LOG_DIR = ROOT_DIR / "logs"
OUT_DIR = ROOT_DIR / "outputs" / "experiments"
LOG_DIR.mkdir(parents=True, exist_ok=True)

APP_THEME = gr.themes.Soft(primary_hue="cyan", secondary_hue="blue")
APP_CSS = """
.gradio-container { max-width: 1540px !important; background: radial-gradient(circle at 8% 8%, #0b1120, #020617 45%, #000 100%) !important; }
.block { border-radius: 14px !important; border: 1px solid rgba(148,163,184,.18) !important; backdrop-filter: blur(8px); }
.hero-card { background: linear-gradient(145deg, rgba(15,23,42,.85), rgba(3,7,18,.85)); border: 1px solid rgba(56,189,248,.22); border-radius: 14px; padding: 14px 16px; color: #e2e8f0; }
.hero-title { font-size: 16px; font-weight: 800; color: #67e8f9; margin-bottom: 8px; }
.summary-grid { display:grid; grid-template-columns:repeat(3,minmax(120px,1fr)); gap:10px; }
.kv .k { color:#94a3b8; font-size:12px; display:block; }
.kv .v { color:#f8fafc; font-weight:700; display:block; margin-top:2px; }
.metric-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:12px; }
.metric-card { border:1px solid rgba(56,189,248,.25); background: linear-gradient(160deg, rgba(15,23,42,.8), rgba(2,6,23,.86)); border-radius:12px; padding:12px; }
.metric-card .mk { color:#94a3b8; font-size:12px; }
.metric-card .mv { color:#f8fafc; font-size:22px; font-weight:800; margin-top:4px; }
.agent-timeline { display:flex; flex-direction:column; gap:10px; }
.agent-card { border:1px solid rgba(148,163,184,.2); background:linear-gradient(160deg, rgba(15,23,42,.85), rgba(30,41,59,.45)); border-radius:12px; padding:10px 12px; }
.agent-head { display:flex; align-items:center; gap:10px; }
.agent-idx { width:22px;height:22px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;background:#0f172a;color:#a5f3fc;border:1px solid rgba(56,189,248,.4); }
.agent-name { flex:1; font-weight:700; color:#e2e8f0; }
.agent-meta { font-size:12px; font-weight:700; }
.agent-bar-wrap { margin-top:8px; background:#0b1220; border-radius:999px; height:8px; overflow:hidden; }
.agent-bar { height:8px; border-radius:999px; }
.agent-trace { margin-top:8px; color:#cbd5e1; font-size:12px; line-height:1.45; }
.replay-wrap { border:1px dashed rgba(103,232,249,.35); border-radius:12px; padding:10px; background:rgba(2,6,23,.55); }
.replay-step { border-left:3px solid #22d3ee; margin:8px 0; padding:6px 10px; color:#cbd5e1; background:rgba(15,23,42,.6); border-radius:6px; animation: fadeInStep .5s ease forwards; opacity:0; }
.replay-step strong { color:#a5f3fc; }
.replay-alert { color:#fca5a5; font-weight:700; margin-top:8px; }
.log-box { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; font-size:12px; line-height:1.4; white-space:pre-wrap; }
@keyframes fadeInStep { from { opacity:0; transform:translateY(4px);} to {opacity:1; transform:translateY(0);} }
"""

RUN_PROCS: Dict[str, Dict[str, Any]] = {}


def _to_jsonable(obj: Any):
    if dataclasses.is_dataclass(obj):
        return {k: _to_jsonable(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(v) for v in obj]
    if hasattr(obj, "value"):
        return obj.value
    return obj


def _tail_text(path: Path, max_lines: int = 120) -> str:
    if not path.exists():
        return f"File not found: {path}"
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    return "\n".join(lines[-max_lines:])


def _discover_latest_metrics(base_dir: Path) -> Optional[Path]:
    candidates = list(base_dir.rglob("metrics.json")) if base_dir.exists() else []
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def _overview_snapshot() -> str:
    metrics_files = list(OUT_DIR.rglob("metrics.json")) if OUT_DIR.exists() else []
    ablation_files = list(OUT_DIR.rglob("ablation_results.json")) if OUT_DIR.exists() else []
    log_files = list(LOG_DIR.glob("run_*.log")) if LOG_DIR.exists() else []

    latest_metrics_path = _discover_latest_metrics(OUT_DIR)
    latest_metrics = {}
    if latest_metrics_path:
        try:
            latest_metrics = json.loads(latest_metrics_path.read_text(encoding="utf-8"))
        except Exception:
            latest_metrics = {}

    def mval(key: str, pct: bool = False) -> str:
        v = latest_metrics.get(key)
        if v is None:
            return "N/A"
        if pct:
            return f"{float(v):.2%}"
        return f"{float(v):.4f}"

    html = f"""
    <div class='hero-card'>
      <div class='hero-title'>System Overview</div>
      <div style='color:#cbd5e1;margin-bottom:10px;'>FinVL-MAS is a multi-agent quantitative finance research system with structured visual reasoning, backtesting, and experiment orchestration.</div>
      <div class='summary-grid'>
        <div class='kv'><span class='k'>Metrics Files</span><span class='v'>{len(metrics_files)}</span></div>
        <div class='kv'><span class='k'>Ablation Files</span><span class='v'>{len(ablation_files)}</span></div>
        <div class='kv'><span class='k'>Run Logs</span><span class='v'>{len(log_files)}</span></div>
        <div class='kv'><span class='k'>Latest Sharpe</span><span class='v'>{mval('sharpe_ratio')}</span></div>
        <div class='kv'><span class='k'>Latest Ann. Return</span><span class='v'>{mval('annualized_return', True)}</span></div>
        <div class='kv'><span class='k'>Latest Dir. Accuracy</span><span class='v'>{mval('directional_accuracy', True)}</span></div>
      </div>
      <div style='margin-top:10px;color:#94a3b8;font-size:12px;'>Latest metrics source: {latest_metrics_path if latest_metrics_path else 'N/A'}</div>
    </div>
    """
    return html


def _workflow_overview_md() -> str:
    return """
## Workflow and Agent Topology

FinVL-MAS executes a structured pipeline:

1. Render chart (optional for VLM path)
2. Extract chart geometry (rule-based + optional VLM)
3. Route evidence across specialist agents
4. Aggregate through shared memory and contradiction detection
5. Emit decision + confidence + rationale

### Agent Sequence
`ChartAnalyst -> PatternReasoner -> EventAnalyst -> RiskController -> DecisionPM`

### What This GUI Exposes
- Decision-level replay from uploaded OHLCV
- Batch run controls for main/ablation/baseline/regime/all
- Metrics/artifacts/log browsing from outputs and logs
- In-app narrative for demos and review sessions
"""


def _list_log_choices() -> List[str]:
    if not LOG_DIR.exists():
        return []
    return sorted([p.name for p in LOG_DIR.glob("*.log")])


def _launch_job(job_type: str, data_path: str, max_dates: int, quick: bool) -> str:
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    script_map = {
        "main": ["bash", "experiments/run_main.sh", data_path, "--max-dates", str(max_dates)],
        "baselines": ["bash", "experiments/run_baselines.sh", data_path],
        "ablations": ["bash", "experiments/run_ablations.sh", data_path, "--max-dates", str(max_dates)],
        "regime": ["bash", "experiments/run_regime_analysis.sh", data_path],
        "all": ["bash", "experiments/run_all.sh", "--data", data_path] + (["--quick"] if quick else []),
        "gui": ["bash", "experiments/launch_gui.sh"],
    }
    if job_type not in script_map:
        return f"Unsupported job type: {job_type}"

    log_name = f"run_{job_type}.log"
    log_path = LOG_DIR / log_name
    log_file = open(log_path, "w", encoding="utf-8")
    proc = subprocess.Popen(script_map[job_type], cwd=str(ROOT_DIR), stdout=log_file, stderr=subprocess.STDOUT, start_new_session=True)

    RUN_PROCS[job_type] = {
        "pid": proc.pid,
        "log": str(log_path),
        "cmd": " ".join(script_map[job_type]),
    }
    return f"Launched `{job_type}` with pid={proc.pid}. Log: {log_path}"


def _job_status_table() -> pd.DataFrame:
    rows = []
    for name, info in sorted(RUN_PROCS.items()):
        pid = int(info.get("pid", -1))
        alive = False
        if pid > 0:
            try:
                os.kill(pid, 0)
                alive = True
            except OSError:
                alive = False
        rows.append({
            "job": name,
            "pid": pid,
            "running": alive,
            "log": info.get("log", ""),
            "cmd": info.get("cmd", ""),
        })
    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=["job", "pid", "running", "log", "cmd"])


def render_interactive_chart(df: pd.DataFrame, geometry: ChartGeometry | None = None, title: str = "Chart") -> go.Figure:
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.75, 0.25], subplot_titles=[title, "Volume"])
    fig.add_trace(go.Candlestick(x=df.index, open=df["open"], high=df["high"], low=df["low"], close=df["close"], name="OHLC", increasing_line_color="#22d3ee", decreasing_line_color="#fb7185"), row=1, col=1)
    colors = ["#22d3ee" if c >= o else "#fb7185" for o, c in zip(df["open"], df["close"])]
    fig.add_trace(go.Bar(x=df.index, y=df["volume"], marker_color=colors, opacity=0.6, name="Volume"), row=2, col=1)

    if len(df) >= 20:
        fig.add_trace(go.Scatter(x=df.index, y=df["close"].rolling(20).mean(), name="SMA20", line=dict(width=1.4, color="#f59e0b")), row=1, col=1)
    if len(df) >= 5:
        fig.add_trace(go.Scatter(x=df.index, y=df["close"].rolling(5).mean(), name="SMA5", line=dict(width=1.4, color="#34d399")), row=1, col=1)

    if geometry:
        for tl in geometry.trendlines:
            if 0 <= tl.start_idx < len(df) and 0 <= tl.end_idx < len(df):
                x0, x1 = df.index[tl.start_idx], df.index[tl.end_idx]
                y0, y1 = tl.slope * tl.start_idx + tl.intercept, tl.slope * tl.end_idx + tl.intercept
                color = "#4ade80" if tl.direction.value == "up" else "#f87171"
                fig.add_shape(type="line", x0=x0, y0=y0, x1=x1, y1=y1, line=dict(color=color, width=2, dash="dash"), row=1, col=1)

        for sr in geometry.support_resistance[:6]:
            color = "#22d3ee" if "support" in sr.level_type else "#fb923c"
            fig.add_hline(y=sr.price, line_dash="dot", line_color=color, opacity=0.6, annotation_text=f"{sr.level_type}:{sr.price:.2f}", row=1, col=1)

    fig.update_layout(template="plotly_dark", height=660, margin=dict(l=24, r=18, t=42, b=24), xaxis_rangeslider_visible=False, legend=dict(orientation="h", y=1.08, x=0.0))
    return fig


def _build_agent_timeline_html(outputs: list[Dict[str, Any]]) -> str:
    cards = []
    for idx, o in enumerate(outputs, 1):
        conf = float(o.get("confidence", 0.0))
        status = "OK" if o.get("success", True) else "ERR"
        color = "#10b981" if conf >= 0.6 else "#f59e0b" if conf >= 0.3 else "#ef4444"
        trace = str(o.get("reasoning_trace") or "no trace")[:320]
        cards.append(f"<div class='agent-card'><div class='agent-head'><div class='agent-idx'>{idx}</div><div class='agent-name'>{o.get('agent_name','Agent')}</div><div class='agent-meta' style='color:{color}'>{status} · {conf:.0%}</div></div><div class='agent-bar-wrap'><div class='agent-bar' style='width:{max(4,int(conf*100))}%; background:{color}'></div></div><div class='agent-trace'>{trace}</div></div>")
    return "<div class='agent-timeline'>" + "".join(cards) + "</div>"


def _build_summary_panel(asset: str, df: pd.DataFrame, decision: Any) -> str:
    action_color = {"buy": "#10b981", "sell": "#ef4444", "hold": "#f59e0b"}.get(decision.action.value, "#94a3b8")
    return f"""
    <div class='hero-card'>
      <div class='hero-title'>Decision Brief</div>
      <div class='summary-grid'>
        <div class='kv'><span class='k'>Asset</span><span class='v'>{asset}</span></div>
        <div class='kv'><span class='k'>Window</span><span class='v'>{df.index[0].strftime('%Y-%m-%d')} → {df.index[-1].strftime('%Y-%m-%d')}</span></div>
        <div class='kv'><span class='k'>Action</span><span class='v' style='color:{action_color};'>{decision.action.value.upper()}</span></div>
        <div class='kv'><span class='k'>Confidence</span><span class='v'>{decision.confidence:.2f}</span></div>
        <div class='kv'><span class='k'>Conviction</span><span class='v'>{decision.conviction.value}</span></div>
        <div class='kv'><span class='k'>Position</span><span class='v'>{decision.position_size_pct:.2%}</span></div>
      </div>
      <div style='margin-top:10px;color:#cbd5e1;'><span class='k'>Rationale</span><div>{decision.rationale}</div></div>
    </div>
    """


def build_replay_story(debug_json: str, speed_ms: int, highlight_disagreements: bool) -> str:
    if not debug_json or not debug_json.strip():
        return "<div class='replay-wrap'>No debug JSON found. Run Decision Studio first.</div>"
    try:
        data = json.loads(debug_json)
    except Exception:
        return "<div class='replay-wrap'>Debug JSON parse failed.</div>"

    lines = [ln.strip() for ln in str(data.get("reasoning_trace", "")).splitlines() if ln.strip()]
    disagreements = data.get("disagreements", []) or []
    if not lines:
        return "<div class='replay-wrap'>No reasoning trace available.</div>"

    sec = max(0.1, float(speed_ms) / 1000.0)
    steps = [f"<div class='replay-step' style='animation-delay:{(i)*sec:.2f}s'><strong>Step {i+1}</strong> · {line}</div>" for i, line in enumerate(lines)]
    tail = ""
    if highlight_disagreements and disagreements:
        tail = "<div class='replay-alert'>Disagreement Flags: " + " | ".join([str(x) for x in disagreements]) + "</div>"
    return "<div class='replay-wrap'>" + "".join(steps) + tail + "</div>"


def _build_vlm_runtime(cfg: Dict[str, Any], selected_model: str, enable_vlm: bool):
    cfg = dict(cfg)
    agent_cfg = dict(cfg.get("agents", {}).get("chart_analyst", {}))
    agent_cfg["use_vlm"] = enable_vlm
    cfg.setdefault("agents", {})["chart_analyst"] = agent_cfg

    vlm_cfg = dict(cfg.get("vlm", {}))
    if selected_model and selected_model != "default":
        vlm_cfg["model"] = selected_model
    cfg["vlm"] = vlm_cfg

    runtime = None
    if enable_vlm:
        api_key = vlm_cfg.get("api_key") or os.getenv("OPENAI_API_KEY")
        if api_key:
            runtime = VLMRouter(vlm_cfg) if vlm_cfg.get("routes") else VLMClient(vlm_cfg)
        else:
            logger.warning("GUI VLM enabled but OPENAI_API_KEY missing; fallback to rule-only mode")
    return cfg, runtime


def analyze_csv(file_obj, lookback: int, asset_name: str, config_path: str, model_name: str, enable_vlm: bool):
    if file_obj is None:
        return None, "<div class='hero-card'>No file uploaded</div>", "", "{}"

    cfg = load_config(config_path) if config_path and Path(config_path).exists() else load_config("configs/default.yaml")
    cfg, vlm_runtime = _build_vlm_runtime(cfg, model_name, enable_vlm)

    df = pd.read_csv(file_obj.name, parse_dates=True, index_col=0)
    df.columns = [c.lower() for c in df.columns]
    for col in ["open", "high", "low", "close", "volume"]:
        if col not in df.columns:
            return None, f"<div class='hero-card'>Missing column: {col}</div>", "", "{}"

    df = df.sort_index().tail(lookback)
    chart_path = None
    with tempfile.TemporaryDirectory(prefix="finvl_gui_") as tmp_dir:
        try:
            from finvl.visual.renderer import ChartRenderer

            renderer = ChartRenderer({**cfg.get("chart", {}), "output_dir": tmp_dir})
            chart_path, _ = renderer.render_candlestick(df, asset=asset_name or "ASSET", save_path=os.path.join(tmp_dir, "input.png"))
        except Exception:
            chart_path = None

        orchestrator = AgentOrchestrator(cfg)
        inputs = {
            "ohlcv_df": df,
            "current_price": float(df["close"].iloc[-1]),
            "asset": asset_name or "ASSET",
            "timeframe": "daily",
            "start_date": df.index[0].strftime("%Y-%m-%d"),
            "end_date": df.index[-1].strftime("%Y-%m-%d"),
            "events": [],
        }
        if chart_path:
            inputs["chart_image_path"] = chart_path
        if chart_path and vlm_runtime is not None:
            inputs["vlm_client"] = vlm_runtime

        decision = asyncio.run(orchestrator.run(inputs))

    memory = orchestrator.get_memory_snapshot()
    geometry = memory.get("chart_geometry") if isinstance(memory.get("chart_geometry"), ChartGeometry) else None
    fig = render_interactive_chart(df, geometry=geometry, title=asset_name or "Analysis")

    summary_html = _build_summary_panel(asset_name or "ASSET", df, decision)
    outputs = [_to_jsonable(dataclasses.asdict(o)) for o in orchestrator.agent_outputs]
    agent_html = _build_agent_timeline_html(outputs)

    debug = {
        "decision": _to_jsonable(decision),
        "memory_snapshot": _to_jsonable(memory),
        "reasoning_trace": orchestrator.get_reasoning_trace(),
        "disagreements": orchestrator.get_disagreements(),
        "vlm_usage": _to_jsonable(vlm_runtime.usage_summary) if vlm_runtime else {},
    }
    return fig, summary_html, agent_html, json.dumps(debug, indent=2)


def load_experiment_results(results_dir: str):
    p = Path(results_dir)
    target = None
    if p.is_file() and p.name == "metrics.json":
        target = p
    elif p.is_dir() and (p / "metrics.json").exists():
        target = p / "metrics.json"
    elif p.is_dir():
        target = _discover_latest_metrics(p)

    if not target or not target.exists():
        return "<p>No metrics.json found</p>", "{}", pd.DataFrame()

    metrics = json.loads(target.read_text(encoding="utf-8"))
    cards = []
    for key in ["sharpe_ratio", "annualized_return", "max_drawdown", "directional_accuracy", "total_return"]:
        v = metrics.get(key, 0)
        txt = f"{v:.2%}" if "return" in key or "drawdown" in key or "accuracy" in key else f"{v:.4f}"
        cards.append(f"<div class='metric-card'><div class='mk'>{key}</div><div class='mv'>{txt}</div></div>")
    html = "<div class='metric-grid'>" + "".join(cards) + "</div>"

    decisions_csv = target.parent / "decisions.csv"
    dec_df = pd.read_csv(decisions_csv) if decisions_csv.exists() else pd.DataFrame()
    return html, json.dumps(metrics, indent=2), dec_df


def _model_options(cfg: Dict[str, Any]) -> list[str]:
    opts = ["default"]
    if cfg.get("vlm", {}).get("model"):
        opts.append(cfg["vlm"]["model"])
    for route in cfg.get("vlm", {}).get("routes", []) or []:
        m = route.get("model")
        if m and m not in opts:
            opts.append(m)
    return opts


def _refresh_logs() -> tuple[gr.Dropdown, str]:
    choices = _list_log_choices()
    return gr.Dropdown(choices=choices, value=choices[0] if choices else None), "Logs refreshed"


def _show_log(log_name: str, lines: int) -> str:
    if not log_name:
        return "No log selected"
    return _tail_text(LOG_DIR / log_name, max_lines=lines)


def _refresh_overview() -> str:
    return _overview_snapshot()


def _launch_from_ui(job_type: str, data_path: str, max_dates: int, quick: bool):
    msg = _launch_job(job_type=job_type, data_path=data_path or "data/processed/synth_daily.csv", max_dates=max_dates, quick=quick)
    table = _job_status_table()
    logs = _list_log_choices()
    dd = gr.Dropdown(choices=logs, value=logs[0] if logs else None)
    return msg, table, dd


def create_app() -> gr.Blocks:
    cfg = load_config("configs/default.yaml") if Path("configs/default.yaml").exists() else {}

    with gr.Blocks(title="FinVL-MAS Decision Studio") as app:
        gr.Markdown(
            """
            # FinVL-MAS Quant Research Studio
            A polished interface for multi-agent visual reasoning, experiment orchestration, and quantitative result analysis.
            """
        )

        with gr.Tabs():
            with gr.Tab("Overview"):
                overview_html = gr.HTML(value=_overview_snapshot(), label="Project Overview")
                refresh_overview_btn = gr.Button("Refresh Overview", variant="secondary")
                workflow_md = gr.Markdown(value=_workflow_overview_md())
                refresh_overview_btn.click(fn=_refresh_overview, inputs=[], outputs=[overview_html])

            with gr.Tab("Decision Studio"):
                with gr.Row():
                    with gr.Column(scale=1):
                        file_input = gr.File(label="Upload OHLCV CSV", file_types=[".csv"])
                        asset_input = gr.Textbox(label="Asset", value="ASSET")
                        lookback = gr.Slider(20, 240, value=60, step=10, label="Lookback")
                        config_path = gr.Textbox(label="Config Path", value="configs/default.yaml")
                        model_name = gr.Dropdown(label="Model", choices=_model_options(cfg), value="default")
                        enable_vlm = gr.Checkbox(label="Enable VLM", value=True)
                        btn = gr.Button("Run Full MAS", variant="primary", size="lg")
                    with gr.Column(scale=3):
                        chart_out = gr.Plot(label="Chart + Geometry + Context")

                with gr.Row():
                    summary_out = gr.HTML(label="Decision Brief")
                    agent_out = gr.HTML(label="Agent Timeline")

                debug_json = gr.Code(language="json", label="Trace / Memory / Usage")

                with gr.Row():
                    replay_speed = gr.Slider(200, 1800, value=700, step=100, label="Replay Step Delay (ms)")
                    replay_disagreement = gr.Checkbox(label="Highlight Disagreements", value=True)
                    replay_btn = gr.Button("Generate CHI Replay", variant="secondary")
                replay_html = gr.HTML(label="Replay Storyboard")

                btn.click(fn=analyze_csv, inputs=[file_input, lookback, asset_input, config_path, model_name, enable_vlm], outputs=[chart_out, summary_out, agent_out, debug_json])
                replay_btn.click(fn=build_replay_story, inputs=[debug_json, replay_speed, replay_disagreement], outputs=[replay_html])

            with gr.Tab("Experiment Control"):
                with gr.Row():
                    with gr.Column(scale=1):
                        job_type = gr.Dropdown(label="Job Type", choices=["main", "baselines", "ablations", "regime", "all", "gui"], value="main")
                        data_path = gr.Textbox(label="Data Path", value="data/processed/synth_daily.csv")
                        max_dates = gr.Slider(10, 400, value=60, step=10, label="Max Dates")
                        quick = gr.Checkbox(label="Quick mode (for all)", value=True)
                        launch_btn = gr.Button("Launch Job", variant="primary")
                    with gr.Column(scale=2):
                        launch_msg = gr.Markdown(label="Launch Status")
                        job_table = gr.Dataframe(value=_job_status_table(), label="Tracked Jobs", interactive=False)
                selected_log = gr.Dropdown(label="Log File", choices=_list_log_choices())
                tail_lines = gr.Slider(20, 400, value=120, step=20, label="Tail Lines")
                with gr.Row():
                    refresh_logs_btn = gr.Button("Refresh Logs")
                    view_log_btn = gr.Button("View Selected Log")
                log_text = gr.Textbox(label="Log Tail", lines=18, elem_classes=["log-box"])

                launch_btn.click(fn=_launch_from_ui, inputs=[job_type, data_path, max_dates, quick], outputs=[launch_msg, job_table, selected_log])
                refresh_logs_btn.click(fn=_refresh_logs, inputs=[], outputs=[selected_log, launch_msg])
                view_log_btn.click(fn=_show_log, inputs=[selected_log, tail_lines], outputs=[log_text])

            with gr.Tab("Results & Analytics"):
                results_dir = gr.Textbox(label="Results Directory or metrics.json Path", value="outputs/experiments")
                load_btn = gr.Button("Load Metrics", variant="primary")
                metrics_cards = gr.HTML(label="Key Metrics")
                metrics_json = gr.Code(language="json", label="metrics.json")
                decisions_df = gr.Dataframe(label="Decisions Table")
                load_btn.click(load_experiment_results, [results_dir], [metrics_cards, metrics_json, decisions_df])

            with gr.Tab("Artifacts & Logs"):
                artifact_md = gr.Markdown(
                    value=(
                        "Use `outputs/experiments` for run artifacts and `logs/*.log` for runtime traces.\n\n"
                        "You can also use the Experiment Control tab for live log tailing."
                    )
                )
                artifact_tree = gr.Textbox(
                    label="Recent Artifact Paths",
                    lines=18,
                    value="\n".join([str(p) for p in sorted(OUT_DIR.rglob("*"))[-80:]])
                    if OUT_DIR.exists()
                    else "No artifacts yet",
                )

            with gr.Tab("System Docs"):
                gr.Markdown(
                    """
                    ## What This System Does
                    FinVL-MAS decomposes quantitative decision-making into specialist agents and coordinates them with shared memory.

                    ## Why This Interface Exists
                    This GUI is designed for demos, reviews, and paper presentations. It exposes real workflows from the repository without backend rewrites.

                    ## Core Entry Points
                    - `experiments/run_main.sh`
                    - `experiments/run_ablations.sh`
                    - `experiments/run_baselines.sh`
                    - `experiments/run_regime_analysis.sh`
                    - `experiments/run_all.sh`
                    - `experiments/launch_gui.sh`
                    """
                )

    return app


def main():
    app = create_app()
    host = os.getenv("FINVL_GUI_HOST", "0.0.0.0")
    port = int(os.getenv("FINVL_GUI_PORT", "7860"))
    share = os.getenv("FINVL_GUI_SHARE", "false").strip().lower() in {"1", "true", "yes", "y"}
    app.launch(server_name=host, server_port=port, share=share, theme=APP_THEME, css=APP_CSS)


if __name__ == "__main__":
    main()
