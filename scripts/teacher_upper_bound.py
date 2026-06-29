"""
Teacher upper-bound diagnostic (principle-level test).

The OPSD teacher is conditioned on PRIVILEGED hindsight: realized risk-adjusted
PnL over the next K days. This script asks the decisive question:

  Under the SAME cost / slippage / T+1 protocol, what is the CEILING of the
  action space when the policy is given perfect hindsight?

If even a perfect-hindsight teacher barely beats Buy&Hold, the bottleneck is the
ACTION SPACE / reward design (no amount of distillation can help the student).
If perfect hindsight dominates, the framework is sound and the bottleneck is the
student's signal/capacity.

We test several hindsight policies per asset and the portfolio:
  - oracle_1d : long iff next-1-day return > 0 (per-day perfect timing)
  - oracle_Kd : long iff next-K-day forward return > 0 (K=20, the teacher signal)
  - oracle_Kd_conf : position scaled by next-K-day risk-adjusted return magnitude
  - buy_hold reference
All with T+1 execution delay and full costs (i.e. hindsight on direction, but
still pay to trade and execute next day).
"""
import sys, json, argparse, warnings
import numpy as np, pandas as pd
from pathlib import Path
warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
import importlib.util
_spec = importlib.util.spec_from_file_location("hv3", str(Path(__file__).parent / "eval_harness_v3.py"))
hv3 = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(hv3)

ASSETS = ["GOOGL", "GS", "JNJ", "NVDA"]
START, END = "2025-01-01", "2025-12-31"
K = 20


def oracle_positions(close, mode, k=K):
    n = len(close); pos = []
    for i in range(n):
        if mode == "oracle_1d":
            fut = (close[i+1] - close[i]) / close[i] if i + 1 < n else 0.0
            pos.append(1.0 if fut > 0 else 0.0)
        elif mode == "oracle_Kd":
            j = min(i + k, n - 1)
            fut = (close[j] - close[i]) / close[i]
            pos.append(1.0 if fut > 0 else 0.0)
        elif mode == "oracle_Kd_ls":  # long-short with perfect K-day direction
            j = min(i + k, n - 1)
            fut = (close[j] - close[i]) / close[i]
            pos.append(1.0 if fut > 0 else -1.0)
    return pos


def main():
    df_all = hv3.load_all()
    import importlib.util as iu
    spec2 = iu.spec_from_file_location("sd", str(Path(__file__).parent / "scan_dow_subset.py"))
    sd = iu.module_from_spec(spec2); spec2.loader.exec_module(sd)
    bl = sd.load_all_baselines()

    agg = {m: [] for m in ["oracle_1d", "oracle_Kd", "oracle_Kd_ls", "buy_hold"]}
    print(f"{'Asset':6} {'oracle_1d':>11} {'oracle_Kd':>11} {'oracle_Kd_ls':>13} {'buy_hold':>10} {'bestBL_SR':>10}")
    for t in ASSETS:
        tdf = df_all[df_all['ticker'] == t].set_index('date').sort_index()
        full = tdf.loc[tdf.index <= pd.Timestamp(END)]
        mask = np.asarray((full.index >= pd.Timestamp(START)) & (full.index <= pd.Timestamp(END)))
        if mask.sum() < 60: continue
        si = int(np.argmax(mask)); prices = full['close'].values.astype(float)[si:]
        row = {}
        for mode in ["oracle_1d", "oracle_Kd", "oracle_Kd_ls"]:
            m = hv3.compute_metrics(oracle_positions(prices, mode), prices)
            row[mode] = m["SR"] if m else None
            if m: agg[mode].append(m)
        bh = hv3.compute_metrics([1.0] * len(prices), prices)
        row["buy_hold"] = bh["SR"] if bh else None
        if bh: agg["buy_hold"].append(bh)
        bsr = max((am[t]["SR"] for nm, am in bl.items() if t in am and am[t]), default=0)
        print(f"{t:6} {row['oracle_1d']:>11.2f} {row['oracle_Kd']:>11.2f} {row['oracle_Kd_ls']:>13.2f} {row['buy_hold']:>10.2f} {bsr:>10.2f}")

    print("\n=== Portfolio mean (ceiling of the action space under cost+T+1) ===")
    for m in ["oracle_1d", "oracle_Kd", "oracle_Kd_ls", "buy_hold"]:
        if agg[m]:
            sr = np.mean([x["SR"] for x in agg[m]]); cr = np.mean([x["CR"] for x in agg[m]])
            md = np.mean([x["MDD"] for x in agg[m]])
            print(f"  {m:14} SR={sr:6.2f} CR={cr:7.1f} MDD={md:6.1f}")
    print("\nInterpretation:")
    print("  If oracle_1d SR is very high but FinOPD~1.8 -> signal/student bottleneck (framework OK).")
    print("  If oracle_Kd (the actual teacher signal) only ~ buy_hold -> reward/action-space bottleneck.")


if __name__ == "__main__":
    main()
