<div align="center">

# FinVL-MAS

**Structured Visual Reasoning over Chart Geometry for Financial Decision Making**

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![NeurIPS 2025](https://img.shields.io/badge/Paper-NeurIPS%202025-orange.svg)](#citation)

*A multi-agent system that operationalizes expert trader visual cognition — extracting structured chart geometry from financial visualizations and routing it through cognitively-specialized reasoning agents coordinated via gated shared memory.*

[Quick Start](#-quick-start) · [Architecture](#-architecture) · [Experiments](#-experiments) · [Dashboard](#-dashboard) · [Paper](#-paper) · [Citation](#citation)

</div>

---

## Overview

**FinVL-MAS** models the cognitive workflow of professional technical traders as a multi-agent AI system. Instead of processing raw OHLCV numbers through sequence encoders, it:

1. **Renders** financial data as candlestick charts with technical overlays
2. **Extracts** structured chart geometry — trendlines, support/resistance levels, candlestick formations, volume patterns
3. **Routes** these visual structures through 5 specialist reasoning agents coordinated via gated shared memory
4. **Produces** trading decisions with interpretable, trader-like rationales
5. **Evaluates** under realistic backtesting with transaction costs and point-in-time constraints

### Central Hypothesis

> Structured visual reasoning over financial chart geometry — when decomposed into specialist cognitive roles and coordinated via shared memory — captures decision-relevant spatial-relational patterns that purely numerical sequence encoders miss, particularly during volatile or pattern-rich market regimes.

---

## Architecture

```
OHLCV Data → Chart Renderer → Geometry Extractor → Multi-Agent Pipeline → Decision
                                     │                      │
                              ┌──────┴──────┐    ┌─────────┴──────────┐
                              │ Rule-Based  │    │ 5 Specialist Agents│
                              │ Trendlines  │    │ ┌─ ChartAnalyst   │
                              │ S/R Levels  │    │ ├─ PatternReasoner │
                              │ Candlestick │    │ ├─ EventAnalyst   │
                              │ Formations  │    │ ├─ RiskController │
                              ├─────────────┤    │ └─ DecisionPM     │
                              │ VLM-Based   │    │                    │
                              │ Holistic    │    │   Shared Memory    │
                              │ Patterns    │    │   (Gated Attn)     │
                              └─────────────┘    └────────────────────┘
```

| Agent | Cognitive Role | Key Outputs |
|-------|---------------|-------------|
| **ChartAnalyst** | Visual perception | Trendlines, S/R levels, patterns, regime |
| **PatternReasoner** | Pattern interpretation | Historical pattern matching, directional bias |
| **EventAnalyst** | Contextual integration | Event impact, fundamental assessment |
| **RiskController** | Risk assessment | Position sizing, stop-loss, risk/reward |
| **DecisionPM** | Decision formation | Buy/Sell/Hold with confidence and rationale |

---

## Quick Start

### 1. Clone and Setup

```bash
git clone <repo-url> FinVL-MAS && cd FinVL-MAS

# Option A: Conda (recommended)
conda env create -f environment.yml
conda activate finvl-mas-mas

# Option B: Pip
pip install -e ".[dev]"
```

### 2. Prepare Data

Place OHLCV data (CSV with columns: `date, open, high, low, close, volume`) in `data/processed/`:

```bash
# Example: download sample data
python -c "
import pandas as pd
df = pd.DataFrame({
    'date': pd.date_range('2020-01-01', periods=500, freq='B'),
    'open': 100 + __import__('numpy').cumsum(__import__('numpy').random.randn(500)*0.5),
    'high': 0, 'low': 0, 'close': 0, 'volume': 0
})
# Fill realistic OHLCV
import numpy as np
df['close'] = df['open'] + np.random.randn(500)*1.0
df['high'] = df[['open','close']].max(axis=1) + abs(np.random.randn(500))*0.3
df['low'] = df[['open','close']].min(axis=1) - abs(np.random.randn(500))*0.3
df['volume'] = (1e6 * (1 + 0.5*np.random.randn(500))).clip(1e4)
df.to_csv('data/processed/sample.csv', index=False)
print('Sample data saved.')
"
```

### 3. Run Analysis (Single Date)

```bash
PYTHONPATH=src python -c "
import asyncio, pandas as pd
from finvl.workflow.orchestrator import AgentOrchestrator

df = pd.read_csv('data/processed/sample.csv', parse_dates=['date'], index_col='date').tail(60)
orch = AgentOrchestrator({'agents': {'chart_analyst': {'use_vlm': False, 'use_rule_based': True}, 'event_analyst': {'stub': True}}})

decision = asyncio.run(orch.run({'ohlcv_df': df, 'current_price': float(df['close'].iloc[-1])}))
print(f'Decision: {decision.action.value} | Confidence: {decision.confidence:.2f}')
print(f'Rationale: {decision.rationale[:200]}')
"
```

### 4. Run Experiments

```bash
# Full paper experiment suite
bash experiments/run_all.sh --data data/processed/csi300_daily.csv

# Individual experiments
bash experiments/run_main.sh data/processed/csi300_daily.csv
bash experiments/run_ablations.sh data/processed/csi300_daily.csv
bash experiments/run_baselines.sh data/processed/csi300_daily.csv
bash experiments/run_regime_analysis.sh data/processed/csi300_daily.csv

# Quick test (30 dates only)
bash experiments/run_all.sh --data data/processed/sample.csv --quick
```

### 5. Launch Dashboard

```bash
# one-command setup + validation
bash todo_exp.sh setup
bash todo_exp.sh smoke

# launch GUI
bash experiments/launch_gui.sh
# or background launch
bash todo_exp.sh gui

# Open http://localhost:7860 in browser
```

### 6. Generate Report

```bash
bash experiments/generate_report.sh outputs/experiments outputs/report.html
# Open outputs/report.html in browser
```

---

## Project Structure

```
FinVL-MAS/
├── src/finvl/                 # Main package
│   ├── core/                  # Types, config, scenario, shared memory
│   ├── agents/                # 5 specialist agents + communication
│   ├── visual/                # Chart rendering, geometry extraction, VLM
│   ├── evaluation/            # Backtesting, metrics, regime analysis
│   ├── workflow/              # Agent orchestrator
│   ├── gui/                   # Gradio dashboard
│   ├── visualization/         # HTML report generator
│   └── utils/                 # Prompts, logging, artifacts
├── src/prompts/               # YAML prompt templates (9 files)
├── configs/                   # Experiment configs + ablations
├── experiments/               # Bash scripts for paper experiments
├── scripts/                   # Python experiment runners
├── papers/                    # LaTeX manuscript + figure prompts
│   ├── sections/              # Paper sections (abstract → conclusion)
│   ├── figure_prompts/        # Detailed drawing specs for each figure
│   └── refs.bib               # Bibliography
├── data/                      # Raw and processed data
├── outputs/                   # Experiment results, reports, logs
└── docs/                      # Developer documentation
```

---

## Experiments

### Main Results
Compares FinVL-MAS against baselines on daily stock prediction tasks.

### Ablation Suite (A1–A8)

| ID | Configuration | Tests |
|---|---|---|
| A1 | Full FinVL-MAS | Complete system |
| A2 | No visual reasoning | Value of visual component |
| A3 | Raw chart, no geometry | Value of structured extraction |
| A4 | Single agent | Value of multi-agent decomposition |
| A5 | No gated memory | Value of gated communication |
| A6 | No event context | Value of non-visual context |
| A7 | No risk controller | Value of explicit risk assessment |
| A8 | Rule-based only | VLM contribution vs. rule-based |

### Evaluation Metrics
- **Prediction**: Directional accuracy, IC, Rank IC
- **Portfolio**: Sharpe ratio (with/without TC), Max drawdown, Calmar ratio, Win rate
- **Robustness**: Regime-conditioned analysis, transaction-cost sensitivity

---

## Dashboard

The interactive Gradio dashboard provides:

- **Overview**: live project snapshot and latest metrics artifacts
- **Decision Studio**: upload OHLCV CSV, run full MAS, inspect chart geometry and agent traces
- **Experiment Control**: launch existing `experiments/*.sh` scripts and tail logs in-app
- **Results & Analytics**: load `metrics.json` and inspect decisions table
- **Artifacts & Logs**: browse generated files and runtime traces
- **System Docs**: in-app architecture and workflow explanations for demos/reviews

Launch with `bash experiments/launch_gui.sh` or `python -m finvl.gui.app`.

---

## Paper

The manuscript scaffold is in `papers/` using NeurIPS 2025 format.

| Section | File | Status |
|---------|------|--------|
| Abstract | `sections/00_abstract.tex` | Draft |
| Introduction | `sections/01_introduction.tex` | Draft |
| Related Work | `sections/02_related_work.tex` | Draft |
| Method | `sections/03_method.tex` | Draft |
| Experiments | `sections/04_experiments.tex` | Skeleton |
| Conclusion | `sections/05_conclusion.tex` | Draft |

Figure drawing prompts (for TikZ/draw.io/AI) are in `papers/figure_prompts/`.

---

## Key Dependencies

| Package | Purpose |
|---------|---------|
| `torch` | Neural network components (gated attention) |
| `pandas`, `numpy`, `scipy` | Data processing and statistics |
| `matplotlib`, `mplfinance` | Chart rendering |
| `plotly` | Interactive visualizations |
| `gradio` | Dashboard GUI |
| `pydantic` | Data validation |
| `openai` | VLM API client (optional) |
| `pandas_ta` | Technical indicators |

---

## Citation

```bibtex
@article{finvlmas2025,
  title={FinVL-MAS: Structured Visual Reasoning over Chart Geometry
         for Financial Decision Making},
  year={2025}
}
```

---

## License

MIT License. See [LICENSE](LICENSE) for details.


---

## GUI Troubleshooting

If `bash experiments/launch_gui.sh` fails, check the following in order:

1. Activate the correct conda environment:

```bash
conda activate finvl-mas-mas
```

2. Ensure GUI dependencies are installed in the same environment:

```bash
pip install gradio plotly matplotlib mplfinance
```

3. Launch from repository root:

```bash
bash experiments/launch_gui.sh
```

4. If VLM is enabled but no API key is provided, the system automatically falls back to rule-only visual analysis. To enable VLM calls, export:

```bash
export OPENAI_API_KEY=your_key
```


---

## Unified Command Pack

You can run setup, smoke tests, experiment launch, and GUI launch from one script:

```bash
bash todo_exp.sh setup
bash todo_exp.sh smoke
bash todo_exp.sh run
bash todo_exp.sh gui
```
