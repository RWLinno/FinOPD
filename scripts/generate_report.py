"""
Generate final HTML report aggregating all experiment results.
Visualizes metrics, evolution curves, ablation comparisons.
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any, Dict, List

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("generate_report")


def load_json_safe(path: str) -> Dict[str, Any]:
    p = Path(path)
    if p.exists():
        with open(p, "r") as f:
            return json.load(f)
    return {}


def load_jsonl(path: str) -> List[Dict]:
    p = Path(path)
    if not p.exists():
        return []
    records = []
    with open(p, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def generate_html_report(
    experiments_dir: str,
    baselines_dir: str,
    evolution_curve_path: str,
    live_forward_dir: str,
    output_path: str,
):
    """Generate comprehensive HTML report."""
    evolution_data = load_jsonl(evolution_curve_path)

    baseline_results = {}
    baselines_path = Path(baselines_dir)
    for f in baselines_path.rglob("baseline_results.json"):
        baseline_results.update(load_json_safe(str(f)))

    live_forward_results = []
    lf_dir = Path(live_forward_dir)
    if lf_dir.exists():
        for f in sorted(lf_dir.glob("*.json")):
            live_forward_results.extend(json.loads(f.read_text()))

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>FinOPD Experiment Report</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 40px; background: #f8f9fa; }}
        h1 {{ color: #1a1a2e; border-bottom: 3px solid #16213e; padding-bottom: 10px; }}
        h2 {{ color: #16213e; margin-top: 30px; }}
        table {{ border-collapse: collapse; width: 100%; margin: 15px 0; background: white; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        th, td {{ border: 1px solid #dee2e6; padding: 8px 12px; text-align: center; }}
        th {{ background: #16213e; color: white; }}
        tr:nth-child(even) {{ background: #f8f9fa; }}
        .metric-card {{ display: inline-block; background: white; padding: 15px 25px; margin: 10px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .metric-value {{ font-size: 24px; font-weight: bold; color: #0f3460; }}
        .metric-label {{ font-size: 12px; color: #666; }}
        .section {{ background: white; padding: 20px; margin: 20px 0; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .highlight {{ color: #04820d; font-weight: bold; }}
    </style>
</head>
<body>
    <h1>FinOPD Experiment Report</h1>
    <p>Generated: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

    <div class="section">
        <h2>Evolution Curve</h2>
        <table>
            <tr><th>Iteration</th><th>Trajectories</th><th>Mean Score</th><th>Belief Store</th><th>Hit Rate</th></tr>
"""

    for record in evolution_data:
        html += f"""            <tr>
                <td>{record.get('iteration', '-')}</td>
                <td>{record.get('num_trajectories', '-')}</td>
                <td>{record.get('mean_score', 0):.4f}</td>
                <td>{record.get('belief_store_size', '-')}</td>
                <td>{record.get('belief_hit_rate', 0):.2%}</td>
            </tr>\n"""

    html += """        </table>
    </div>

    <div class="section">
        <h2>Baseline Comparison</h2>
        <table>
            <tr><th>Method</th><th>Sharpe</th><th>Return</th><th>MDD</th><th>Win Rate</th></tr>
"""

    for name, metrics in baseline_results.items():
        sr = metrics.get("sharpe_ratio", 0)
        ret = metrics.get("annualized_return", 0)
        mdd = metrics.get("max_drawdown", 0)
        wr = metrics.get("win_rate", 0)
        html += f"            <tr><td>{name}</td><td>{sr:.4f}</td><td>{ret:.2%}</td><td>{mdd:.2%}</td><td>{wr:.2%}</td></tr>\n"

    html += """        </table>
    </div>

    <div class="section">
        <h2>Live-Forward Results</h2>
        <table>
            <tr><th>Date</th><th>Ticker</th><th>Action</th><th>Confidence</th><th>Price</th></tr>
"""

    for result in live_forward_results[-20:]:
        html += f"""            <tr>
                <td>{result.get('date', '-')}</td>
                <td>{result.get('ticker', '-')}</td>
                <td>{result.get('action', '-')}</td>
                <td>{result.get('confidence', 0):.2f}</td>
                <td>{result.get('current_price', '-')}</td>
            </tr>\n"""

    html += """        </table>
    </div>
</body>
</html>"""

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")
    logger.info(f"Report generated: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Generate FinOPD Final Report")
    parser.add_argument("--experiments-dir", default="outputs/experiments/")
    parser.add_argument("--baselines-dir", default="outputs/experiments/")
    parser.add_argument("--evolution-curve", default="outputs/opsd_full/evolution_curve.jsonl")
    parser.add_argument("--live-forward-dir", default="outputs/live_forward/")
    parser.add_argument("--output", default="outputs/final_report.html")
    args = parser.parse_args()

    generate_html_report(
        experiments_dir=args.experiments_dir,
        baselines_dir=args.baselines_dir,
        evolution_curve_path=args.evolution_curve,
        live_forward_dir=args.live_forward_dir,
        output_path=args.output,
    )


if __name__ == "__main__":
    main()
