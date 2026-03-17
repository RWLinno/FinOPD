"""
Generate figures and tables for the FinVL-MAS paper.
Reads experiment results and produces LaTeX-ready assets.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from finvl.evaluation.analysis import format_metrics_table


def generate_latex_table(results: dict, caption: str, label: str) -> str:
    """Generate a LaTeX table from results dict."""
    metrics = ["sharpe_ratio", "annualized_return", "max_drawdown",
               "information_coefficient", "directional_accuracy"]
    header = " & ".join(["Method"] + [m.replace("_", " ").title() for m in metrics])

    rows = []
    for name, m in results.items():
        vals = []
        for metric in metrics:
            v = m.get(metric, 0.0)
            if isinstance(v, float):
                vals.append(f"{v:.4f}")
            else:
                vals.append(str(v))
        rows.append(f"  {name} & " + " & ".join(vals) + r" \\")

    return (
        r"\begin{table}[h]" + "\n"
        r"\centering" + "\n"
        r"\caption{" + caption + "}\n"
        r"\label{" + label + "}\n"
        r"\begin{tabular}{l" + "c" * len(metrics) + "}\n"
        r"\toprule" + "\n"
        f"  {header}" + r" \\" + "\n"
        r"\midrule" + "\n"
        + "\n".join(rows) + "\n"
        r"\bottomrule" + "\n"
        r"\end{tabular}" + "\n"
        r"\end{table}"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", required=True, help="Experiment results directory")
    parser.add_argument("--output-dir", default="papers/tables")
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Main results
    metrics_path = results_dir / "metrics.json"
    if metrics_path.exists():
        with open(metrics_path) as f:
            metrics = json.load(f)
        table = generate_latex_table(
            {"FinVL-MAS": metrics},
            "Main experimental results on test set.",
            "tab:main_results",
        )
        (output_dir / "main_results.tex").write_text(table)
        print(f"Main results table saved to {output_dir / 'main_results.tex'}")

    # Ablation results
    ablation_path = results_dir / "ablation_results.json"
    if ablation_path.exists():
        with open(ablation_path) as f:
            ablation = json.load(f)
        table = generate_latex_table(
            ablation,
            "Ablation study results.",
            "tab:ablation",
        )
        (output_dir / "ablation_results.tex").write_text(table)
        print(f"Ablation table saved to {output_dir / 'ablation_results.tex'}")


if __name__ == "__main__":
    main()
