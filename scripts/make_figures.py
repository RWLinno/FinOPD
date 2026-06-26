"""
Generate publication-quality figures from real FinOPD results.
Unified style (consistent palette, fonts, grid). Writes PNGs to
KDD27_FinOPD_overleaf/figures/.

Usage: python scripts/make_figures.py
"""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager  # noqa

SNAP = Path("KDD27_FinOPD_overleaf/data_snapshots")
FIG = Path("KDD27_FinOPD_overleaf/figures")
FIG.mkdir(parents=True, exist_ok=True)

# ---- unified style ----
plt.rcParams.update({
    "figure.dpi": 200, "savefig.dpi": 200,
    "font.size": 11, "font.family": "DejaVu Sans",
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": "#e6e8ee", "grid.linewidth": 0.8,
    "axes.edgecolor": "#444", "axes.linewidth": 0.9,
    "axes.titlesize": 12, "axes.titleweight": "bold",
})
ACC = "#2f6df0"; OURS = "#1b4fd8"; BASE = "#9aa3b2"; GOOD = "#1aa260"; WARN = "#d9863a"; BAD = "#d65a5a"


def load(n):
    p = SNAP / n
    return json.load(open(p)) if p.exists() else {}


def fig_main_bars():
    ssot = load("ssot_v3_main.json").get("results", {})
    methods = ["Buy & Hold", "SMA Cross", "PatchTST", "TimesNet", "iTransformer",
               "TradingAgents", "FinCon", "R&D-Agent", "AlphaAgent", "FinOPD"]
    agg = {}
    for m in methods:
        v = [ssot[a][m] for a in ssot if m in ssot[a]]
        if v:
            agg[m] = (float(np.mean([x["SR"] for x in v])), float(np.mean([x["MDD"] for x in v])))
    order = sorted(agg.items(), key=lambda x: x[1][0])
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.2))
    labels = [k for k, _ in order]
    srs = [v[0] for _, v in order]
    cols = [OURS if k == "FinOPD" else BASE for k in labels]
    ax1.barh(labels, srs, color=cols)
    ax1.set_title("Portfolio Sharpe (full-year 2025)")
    ax1.set_xlabel("Sharpe ratio")
    for i, s in enumerate(srs):
        ax1.text(s + 0.02, i, f"{s:.2f}", va="center", fontsize=9,
                 color=OURS if labels[i] == "FinOPD" else "#666")
    for k, (sr, md) in agg.items():
        ax2.scatter(md, sr, s=90 if k == "FinOPD" else 55,
                    color=OURS if k == "FinOPD" else BASE, zorder=3,
                    edgecolor="white", linewidth=0.8)
        ax2.annotate(k, (md, sr), fontsize=8, xytext=(4, 4),
                     textcoords="offset points", color="#444")
    ax2.set_title("Risk-return profile")
    ax2.set_xlabel("Max drawdown %"); ax2.set_ylabel("Sharpe ratio")
    fig.tight_layout(); fig.savefig(FIG / "fig_main_results.png"); plt.close(fig)
    print("wrote fig_main_results.png")


def fig_multiwindow():
    mw = load("multiwindow.json")
    wins = list(mw.keys())
    fo = [mw[w]["FinOPD"]["SR"] if "FinOPD" in mw[w] else None for w in wins]
    # rank of FinOPD per window
    ranks = []
    for w in wins:
        agg = mw[w]; fos = agg["FinOPD"]["SR"]
        r = 1 + sum(1 for m, v in agg.items() if m != "FinOPD" and v["SR"] > fos)
        ranks.append(r)
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(wins, fo, "-o", color=OURS, linewidth=2.2, markersize=7, label="FinOPD Sharpe")
    ax.fill_between(range(len(wins)), 0, fo, color=ACC, alpha=0.10)
    for i, (s, r) in enumerate(zip(fo, ranks)):
        ax.annotate(f"#{r}", (i, s), xytext=(0, 8), textcoords="offset points",
                    ha="center", fontsize=10, fontweight="bold",
                    color=GOOD if r == 1 else "#444")
    ax.set_title("Multi-window robustness (rank among 11 methods)")
    ax.set_ylabel("Portfolio Sharpe"); ax.set_ylim(0, max(fo) * 1.25)
    ax.legend(frameon=False)
    fig.tight_layout(); fig.savefig(FIG / "fig_multiwindow.png"); plt.close(fig)
    print("wrote fig_multiwindow.png")


def fig_ablation():
    abl = load("real_ablation.json")
    items = [(k.replace("A2_", "").replace("A4_", "").replace("A7_", "")
              .replace("A8_", "").replace("A10_", "").replace("_", " "), v.get("dSR", 0))
             for k, v in abl.items() if k != "A1_full"]
    items.sort(key=lambda x: x[1])
    fig, ax = plt.subplots(figsize=(7, 4))
    cols = [BAD if d < -0.2 else (WARN if d < -0.05 else BASE) for _, d in items]
    ax.barh([k for k, _ in items], [d for _, d in items], color=cols)
    ax.axvline(0, color="#444", linewidth=0.8)
    ax.set_title("Ablation: \u0394Sharpe when removing each component")
    ax.set_xlabel("\u0394 Sharpe vs full system")
    for i, (_, d) in enumerate(items):
        ax.text(d - 0.01 if d < 0 else d + 0.01, i, f"{d:+.2f}", va="center",
                ha="right" if d < 0 else "left", fontsize=9, color="#444")
    fig.tight_layout(); fig.savefig(FIG / "fig_ablation.png"); plt.close(fig)
    print("wrote fig_ablation.png")


def fig_sensitivity():
    sens = load("real_sensitivity.json")
    tp = [(float(k.split("_")[1]), v["SR"]) for k, v in sens.items() if k.startswith("tp_") and v]
    sl = [(float(k.split("_")[1]), v["SR"]) for k, v in sens.items() if k.startswith("sl_") and v]
    tp.sort(); sl.sort()
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot([x for x, _ in tp], [y for _, y in tp], "-o", color=OURS, label="take-profit", linewidth=2)
    ax.plot([x for x, _ in sl], [y for _, y in sl], "-s", color=GOOD, label="stop-loss", linewidth=2)
    ax.set_title("Hyperparameter sensitivity (portfolio Sharpe)")
    ax.set_xlabel("threshold"); ax.set_ylabel("Sharpe"); ax.legend(frameon=False)
    fig.tight_layout(); fig.savefig(FIG / "fig_sensitivity.png"); plt.close(fig)
    print("wrote fig_sensitivity.png")


if __name__ == "__main__":
    fig_main_bars(); fig_multiwindow(); fig_ablation(); fig_sensitivity()
    print("All figures written to", FIG)
