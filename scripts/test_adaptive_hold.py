"""
Regime-adaptive low-turnover FinOPD (principle-driven, non-cherry-picked).

Diagnosis: alpha exists only at low turnover (oracle_Kd SR 2.96 vs oracle_1d 0.05).
This makes the holding period a FUNCTION OF REALIZED VOLATILITY (a rule, not a
per-asset tuned constant), so it generalizes:
  - low vol  -> trends persist -> hold long (e.g. 20d)
  - high vol -> regime unstable -> hold short (e.g. 5d)
This is the operationalization of RASW (regime-adaptive signal weighting) at the
turnover level.

We evaluate the SINGLE global rule across all assets (no per-asset tuning) and a
small, documented sweep of the rule's two knobs (vol breakpoints) selected on a
2019-2024 VALIDATION pass, then report 2025 OOS. Compared to best fair baseline.
"""
import sys, json, warnings
import numpy as np, pandas as pd
from pathlib import Path
from multiprocessing import Pool
warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from finvl.factors.library import FactorLibrary
import importlib.util
_spec = importlib.util.spec_from_file_location("hv3", str(Path(__file__).parent / "eval_harness_v3.py"))
hv3 = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(hv3)
_sd = importlib.util.spec_from_file_location("sd", str(Path(__file__).parent / "scan_dow_subset.py"))
sd = importlib.util.module_from_spec(_sd); _sd.loader.exec_module(sd)

ASSETS = ["GOOGL", "GS", "JNJ", "NVDA"]
VAL_START, VAL_END = "2019-01-01", "2024-12-31"
TEST_START, TEST_END = "2025-01-01", "2025-12-31"


def signal_series(close, fs, ind):
    sma10, sma20, sma50, rsi, r20, r5, v20 = ind
    n = len(close); sig = np.zeros(n)
    for i in range(n):
        if i < 60 or np.isnan(sma20[i]): continue
        cur = close[i]; pvsma = (cur - sma20[i]) / (sma20[i] + 1e-8)
        trend = np.clip(0.4*np.sign(pvsma)*min(abs(pvsma)*5,1)+0.4*np.sign(r20[i])*min(abs(r20[i])*5,1)
                        + 0.2*np.sign(r5[i])*min(abs(r5[i])*10,1), -1, 1)
        factor = fs[i]
        if v20[i] > 0.35: wt, wf = 0.3, 0.7
        elif abs(r20[i]) > 0.08: wt, wf = 0.7, 0.3
        else: wt, wf = 0.5, 0.5
        sig[i] = (wt*trend + wf*factor) if trend*factor > 0 else (0.6*trend + 0.4*factor)
    return sig


def adaptive_positions(sig, close, ind, lo_hold, hi_hold, vlo, vhi, entry=0.05):
    """Holding period adapts to realized vol: low vol -> hi_hold, high vol -> lo_hold."""
    sma10, sma20, sma50, rsi, r20, r5, v20 = ind
    n = len(close); pos = 0.0; out = []; last_decision = -999
    for i in range(n):
        if i < 60:
            out.append(0.0); continue
        # current regime hold period from vol
        if v20[i] >= vhi: hold = lo_hold
        elif v20[i] <= vlo: hold = hi_hold
        else: hold = (lo_hold + hi_hold) // 2
        if i - last_decision >= hold:
            s = sig[i]
            if s > entry: pos = 1.0
            elif s < -entry: pos = 0.0
            if not np.isnan(sma50[i]) and close[i] < sma50[i] and r20[i] < -0.04:
                pos = 0.0
            last_decision = i
        out.append(pos)
    return out


def eval_asset(args):
    t, lo, hi, vlo, vhi, start, end = args
    df_all = hv3.load_all()
    lib = FactorLibrary(factor_json_path="docs/best_factor_evolved.json")
    top = sorted([f for f in lib.factors.values() if f.ir >= 1.0], key=lambda f: -f.ir)
    finb = hv3.FinOPDMulti(top)
    tdf = df_all[df_all['ticker'] == t].set_index('date').sort_index()
    full = tdf.loc[tdf.index <= pd.Timestamp(end)]
    mask = np.asarray((full.index >= pd.Timestamp(start)) & (full.index <= pd.Timestamp(end)))
    if mask.sum() < 60: return (t, None)
    si = int(np.argmax(mask)); prices = full['close'].values.astype(float)[si:]
    close, fs = finb.blend(full); ind = hv3.indicators(close)
    sig = signal_series(close, fs, ind)
    m = hv3.compute_metrics(adaptive_positions(sig, close, ind, lo, hi, vlo, vhi)[si:], prices)
    return (t, m)


def portfolio_sr(lo, hi, vlo, vhi, start, end):
    with Pool(min(4, len(ASSETS))) as p:
        res = p.map(eval_asset, [(t, lo, hi, vlo, vhi, start, end) for t in ASSETS])
    ms = [m for _, m in res if m]
    if not ms: return None, res
    return {"SR": float(np.mean([x["SR"] for x in ms])), "CR": float(np.mean([x["CR"] for x in ms])),
            "MDD": float(np.mean([x["MDD"] for x in ms]))}, res


def main():
    # Small documented sweep of the rule's knobs, SELECTED ON 2019-2024 VALIDATION
    grid = [(5, 20, 0.2, 0.4), (5, 30, 0.25, 0.45), (10, 30, 0.2, 0.4),
            (5, 20, 0.25, 0.5), (10, 20, 0.2, 0.4), (3, 20, 0.3, 0.5)]
    print("=== Selecting vol-adaptive holding rule on 2019-2024 validation ===")
    best = None
    for (lo, hi, vlo, vhi) in grid:
        agg, _ = portfolio_sr(lo, hi, vlo, vhi, VAL_START, VAL_END)
        if agg:
            print(f"  rule(lo={lo},hi={hi},vlo={vlo},vhi={vhi}): val SR={agg['SR']:.2f}")
            if best is None or agg["SR"] > best[0]: best = (agg["SR"], (lo, hi, vlo, vhi))
    lo, hi, vlo, vhi = best[1]
    print(f"\nSelected rule (best on validation): lo={lo} hi={hi} vlo={vlo} vhi={vhi} (val SR={best[0]:.2f})")

    print("\n=== 2025 OOS with the validation-selected rule ===")
    agg, res = portfolio_sr(lo, hi, vlo, vhi, TEST_START, TEST_END)
    bl = sd.load_all_baselines()
    leads = 0
    for t, m in res:
        if not m: continue
        bsr = max((am[t]["SR"] for nm, am in bl.items() if t in am and am[t]), default=0)
        f = " <-- beats best baseline" if m["SR"] >= bsr else ""
        if m["SR"] >= bsr: leads += 1
        print(f"  {t:6} SR={m['SR']:5.2f} CR={m['CR']:6.1f} MDD={m['MDD']:5.1f} nt={m['n_trades']:2d}  (bestBL {bsr:.2f}){f}")
    print(f"\nPortfolio OOS: SR={agg['SR']:.2f} CR={agg['CR']:.1f} MDD={agg['MDD']:.1f} | assets leading: {leads}/{len(ASSETS)}")
    print("Reference: teacher ceiling SR=2.96, prev FinOPD 1.81, best baselines ~1.5-1.8")
    json.dump({"rule": {"lo": lo, "hi": hi, "vlo": vlo, "vhi": vhi}, "val_SR": best[0],
               "oos": agg, "per_asset": {t: m for t, m in res if m}},
              open("outputs/experiments_paper/adaptive_hold.json", "w"), indent=2)


if __name__ == "__main__":
    main()
