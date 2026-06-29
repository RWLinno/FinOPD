"""
Low-turnover FinOPD test (principle-driven optimization).

Diagnosis showed: oracle_1d (daily perfect timing) SR=0.05 (costs kill it), but
oracle_Kd (20-day horizon, the teacher's signal scale) SR=2.96. So the action
space only has alpha at LOW turnover. This tests whether a FinOPD policy that
holds for ~K days (instead of reacting daily) climbs toward the teacher ceiling.

FinOPD signal = trend + IR-weighted factor blend (same as deployed), but the
position is only allowed to CHANGE every `hold` days (decision throttling), and
we sweep hold in {1,5,10,20,30} and entry thresholds. Compared to the best fair
baseline per asset and at portfolio level.
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
_sd = importlib.util.spec_from_file_location("sd", str(Path(__file__).parent / "scan_dow_subset.py"))
sd = importlib.util.module_from_spec(_sd); _sd.loader.exec_module(sd)

ASSETS = ["GOOGL", "GS", "JNJ", "NVDA"]
START, END = "2025-01-01", "2025-12-31"
HOLDS = [1, 5, 10, 20, 30]


def signal_series(close, fs, ind):
    """Continuous conviction score in [-1,1] from trend + factor blend (deployed logic)."""
    sma10, sma20, sma50, rsi, r20, r5, v20 = ind
    n = len(close); sig = np.zeros(n)
    for i in range(n):
        if i < 60 or np.isnan(sma20[i]):
            continue
        cur = close[i]; pvsma = (cur - sma20[i]) / (sma20[i] + 1e-8)
        trend = np.clip(0.4*np.sign(pvsma)*min(abs(pvsma)*5,1)+0.4*np.sign(r20[i])*min(abs(r20[i])*5,1)
                        + 0.2*np.sign(r5[i])*min(abs(r5[i])*10,1), -1, 1)
        factor = fs[i]
        if v20[i] > 0.35: wt, wf = 0.3, 0.7
        elif abs(r20[i]) > 0.08: wt, wf = 0.7, 0.3
        else: wt, wf = 0.5, 0.5
        sig[i] = (wt*trend + wf*factor) if trend*factor > 0 else (0.6*trend + 0.4*factor)
    return sig


def throttled_positions(sig, close, ind, hold, entry=0.05):
    """Position changes only every `hold` days; long if conviction>entry, flat if <-entry."""
    sma10, sma20, sma50, rsi, r20, r5, v20 = ind
    n = len(close); pos = 0.0; out = []
    for i in range(n):
        if i < 60:
            out.append(0.0); continue
        if i % hold == 0:  # decision day
            s = sig[i]
            if s > entry: pos = 1.0
            elif s < -entry: pos = 0.0
            # trend-break guard still active on decision days
            if not np.isnan(sma50[i]) and close[i] < sma50[i] and r20[i] < -0.04:
                pos = 0.0
        out.append(pos)
    return out


def main():
    df_all = hv3.load_all()
    lib = FactorLibrary(factor_json_path="docs/best_factor_evolved.json")
    top = sorted([f for f in lib.factors.values() if f.ir >= 1.0], key=lambda f: -f.ir)
    finb = hv3.FinOPDMulti(top)
    bl = sd.load_all_baselines()

    port = {h: [] for h in HOLDS}
    for t in ASSETS:
        tdf = df_all[df_all['ticker'] == t].set_index('date').sort_index()
        full = tdf.loc[tdf.index <= pd.Timestamp(END)]
        mask = np.asarray((full.index >= pd.Timestamp(START)) & (full.index <= pd.Timestamp(END)))
        if mask.sum() < 60: continue
        si = int(np.argmax(mask)); prices = full['close'].values.astype(float)[si:]
        close, fs = finb.blend(full); ind = hv3.indicators(close)
        sig = signal_series(close, fs, ind)
        bsr = max((am[t]["SR"] for nm, am in bl.items() if t in am and am[t]), default=0)
        print(f"\n=== {t} (best baseline SR={bsr:.2f}) ===")
        for h in HOLDS:
            m = hv3.compute_metrics(throttled_positions(sig, close, ind, h)[si:], prices)
            if m:
                port[h].append(m)
                flag = " <-- beats best baseline" if m["SR"] >= bsr else ""
                print(f"  hold={h:2}d  SR={m['SR']:5.2f} CR={m['CR']:6.1f} MDD={m['MDD']:5.1f} nt={m['n_trades']:2d}{flag}")

    print("\n=== Portfolio mean by holding period ===")
    best = None
    for h in HOLDS:
        if port[h]:
            sr = np.mean([x["SR"] for x in port[h]]); cr = np.mean([x["CR"] for x in port[h]])
            md = np.mean([x["MDD"] for x in port[h]])
            print(f"  hold={h:2}d  SR={sr:5.2f} CR={cr:6.1f} MDD={md:5.1f} Calmar={cr/md:.2f}")
            if best is None or sr > best[1]: best = (h, sr)
    print(f"\nBest holding period: {best[0]}d (portfolio SR={best[1]:.2f}); teacher ceiling SR=2.96, baselines ~1.5-1.8")


if __name__ == "__main__":
    main()
