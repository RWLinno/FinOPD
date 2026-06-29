"""
Test whether FinOPD can match/beat the strong baselines by incorporating the
clean trend-filter "trick" (SMA20>SMA50 + RSI gate) that the FinCon/AlphaAgent
proxies use, fused with FinOPD's factor consensus + scaling.

Compares several FinOPD decision variants per asset against the best fair baseline.
"""
import sys, json, warnings
import numpy as np, pandas as pd
from pathlib import Path
warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from finvl.factors.library import FactorLibrary
import importlib.util
_spec = importlib.util.spec_from_file_location("hv3", str(Path(__file__).parent / "eval_harness_v3.py"))
hv3 = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(hv3)

ASSETS = ["GOOGL", "GS", "JNJ", "NVDA", "AAPL", "MSFT", "WMT", "HD"]
START, END = "2025-01-01", "2025-12-31"


def fused_positions(close, fs, ind, mode):
    """mode controls the decision rule:
       'trend'  = clean trend filter (FinCon trick): long iff close>sma20>sma50 & rsi<70
       'fused'  = trend filter AND factor consensus agree
       'trend_factor' = trend filter, size scaled by factor agreement
    """
    sma10, sma20, sma50, rsi, r20, r5, v20 = ind
    n = len(close); pos = 0.0; out = []
    for i in range(n):
        if i < 60 or np.isnan(sma50[i]):
            out.append(pos if i >= 60 else 0.0); continue
        cur = close[i]
        uptrend = cur > sma20[i] > sma50[i] and rsi[i] < 70
        downtrend = rsi[i] > 75 or cur < sma50[i]
        factor = fs[i]
        if mode == 'trend':
            if uptrend: pos = 1.0
            elif downtrend: pos = 0.0
        elif mode == 'fused':
            if uptrend and factor > 0: pos = 1.0
            elif downtrend or factor < -0.1: pos = 0.0
        elif mode == 'trend_factor':
            if uptrend:
                pos = 1.0 if factor > 0 else 0.6
            elif downtrend: pos = 0.0
        out.append(max(min(pos, 1.0), 0.0))
    return out


def main():
    df_all = hv3.load_all()
    lib = FactorLibrary(factor_json_path="docs/best_factor_evolved.json")
    top = sorted([f for f in lib.factors.values() if f.ir >= 1.0], key=lambda f: -f.ir)
    finblend = hv3.FinOPDMulti(top)
    # baselines
    import importlib.util as iu
    spec2 = iu.spec_from_file_location("sd", str(Path(__file__).parent / "scan_dow_subset.py"))
    sd = iu.module_from_spec(spec2); spec2.loader.exec_module(sd)
    bl = sd.load_all_baselines()

    for t in ASSETS:
        tdf = df_all[df_all['ticker'] == t].set_index('date').sort_index()
        full = tdf.loc[tdf.index <= pd.Timestamp(END)]
        mask = np.asarray((full.index >= pd.Timestamp(START)) & (full.index <= pd.Timestamp(END)))
        if mask.sum() < 60: continue
        si = int(np.argmax(mask)); prices = full['close'].values.astype(float)[si:]
        close, fs = finblend.blend(full); ind = hv3.indicators(close)
        # best baseline SR for this asset
        bsr = max((am[t]["SR"] for nm, am in bl.items() if t in am and am[t]), default=0)
        bname = max(((am[t]["SR"], nm) for nm, am in bl.items() if t in am and am[t]), default=(0, "?"))[1]
        print(f"\n=== {t} (best baseline {bname} SR={bsr:.2f}) ===")
        for mode in ['trend', 'fused', 'trend_factor']:
            m = hv3.compute_metrics(fused_positions(close, fs, ind, mode)[si:], prices)
            if m:
                cal = m["CR"]/m["MDD"] if m["MDD"]>1e-9 else 0
                flag = "  <-- beats best SR" if m["SR"] >= bsr else ""
                print(f"  FinOPD[{mode:13}] SR={m['SR']:5.2f} CR={m['CR']:6.1f} MDD={m['MDD']:5.1f} Cal={cal:5.2f} nt={m['n_trades']}{flag}")


if __name__ == "__main__":
    main()
