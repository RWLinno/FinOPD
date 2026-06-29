"""
Fast per-asset walk-forward (cached blend). For each asset, compute the factor
blend + indicators ONCE, then sweep holding/vol/entry configs over both the
2019-2024 validation window and 2025 OOS. Select config by validation Sharpe,
report OOS, and count wins on the three reported metrics (CR/SR/Calmar) vs all
fair baselines. Honest: config chosen without seeing 2025.
"""
import sys, json, warnings, itertools
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

ASSETS = ["GOOGL", "GS", "JNJ", "NVDA", "MSFT", "AAPL", "JPM", "V", "HD", "MCD", "KO", "IBM", "CSCO", "XOM", "WMT", "MRK"]
VAL_START, VAL_END = "2019-01-01", "2024-12-31"
TEST_START, TEST_END = "2025-01-01", "2025-12-31"
GRID = list(itertools.product([3, 5, 10], [10, 20, 30], [(0.20, 0.40), (0.25, 0.45)], [0.03, 0.05, 0.08]))


def gen_positions(close, fs, ind, cfg):
    lo, hi, (vlo, vhi), entry = cfg
    sma10, sma20, sma50, rsi, r20, r5, v20 = ind
    n = len(close); pos = 0.0; out = []; last = -999
    for i in range(n):
        if i < 60 or np.isnan(sma20[i]):
            out.append(pos if i >= 60 else 0.0); continue
        cur = close[i]; pvsma = (cur - sma20[i]) / (sma20[i] + 1e-8)
        trend = np.clip(0.4*np.sign(pvsma)*min(abs(pvsma)*5,1)+0.4*np.sign(r20[i])*min(abs(r20[i])*5,1)
                        + 0.2*np.sign(r5[i])*min(abs(r5[i])*10,1), -1, 1)
        factor = fs[i]
        if v20[i] > 0.35: wt, wf = 0.3, 0.7
        elif abs(r20[i]) > 0.08: wt, wf = 0.7, 0.3
        else: wt, wf = 0.5, 0.5
        score = (wt*trend + wf*factor) if trend*factor > 0 else (0.6*trend + 0.4*factor)
        if v20[i] >= vhi: hold = lo
        elif v20[i] <= vlo: hold = hi
        else: hold = (lo + hi) // 2
        if i - last >= hold:
            if score > entry: pos = 1.0
            elif score < -entry: pos = 0.0
            if not np.isnan(sma50[i]) and cur < sma50[i] and r20[i] < -0.04:
                pos = 0.0
            last = i
        out.append(max(min(pos, 1.0), 0.0))
    return out


def metr(close_full, idx_lo, idx_hi, fs, ind, cfg):
    pos = gen_positions(close_full, fs, ind, cfg)
    seg = pos[idx_lo:idx_hi]; prices = close_full[idx_lo:idx_hi]
    return hv3.compute_metrics(seg, prices)


def main():
    df_all = hv3.load_all()
    lib = FactorLibrary(factor_json_path="docs/best_factor_evolved.json")
    top = sorted([f for f in lib.factors.values() if f.ir >= 1.0], key=lambda f: -f.ir)
    fin = hv3.FinOPDMulti(top)
    bl = sd.load_all_baselines()
    results = {}; allwin = []
    for t in ASSETS:
        tdf = df_all[df_all['ticker'] == t].set_index('date').sort_index()
        if len(tdf) < 400: continue
        close_full, fs = fin.blend(tdf)          # ONE blend per asset
        ind = hv3.indicators(close_full)
        idx = tdf.index
        v0 = int(np.argmax(np.asarray(idx >= pd.Timestamp(VAL_START))))
        v1 = int(np.argmax(np.asarray(idx > pd.Timestamp(VAL_END))))
        t0 = int(np.argmax(np.asarray(idx >= pd.Timestamp(TEST_START))))
        t1 = len(idx)
        # select on validation
        best = None
        for cfg in GRID:
            m = metr(close_full, v0, v1, fs, ind, cfg)
            if m and (best is None or m["SR"] > best[0]): best = (m["SR"], cfg)
        cfg = best[1]
        m = metr(close_full, t0, t1, fs, ind, cfg)
        if not m: continue
        comps = [am[t] for nm, am in bl.items() if t in am and am[t]]
        bsr = max(v["SR"] for v in comps); bcr = max(v["CR"] for v in comps)
        bcal = max((v["CR"]/v["MDD"] if v["MDD"]>1e-9 else -9) for v in comps)
        cal = m["CR"]/m["MDD"] if m["MDD"]>1e-9 else 0
        wins = sum([m["CR"]>=bcr, m["SR"]>=bsr, cal>=bcal])
        m["Calmar"] = round(cal, 2); m["wins3"] = wins; m["cfg"] = list(cfg[:2])+[list(cfg[2]),cfg[3]]
        results[t] = m
        if wins == 3: allwin.append(t)
        print(f"{t:6} cfg{cfg[0],cfg[1],cfg[2],cfg[3]} | SR={m['SR']:.2f}(bl{bsr:.2f}) CR={m['CR']:.1f}(bl{bcr:.1f}) Cal={cal:.2f}(bl{bcal:.2f}) -> {wins}/3{'  ALL3' if wins==3 else ''}")
    print(f"\nAll-3-win assets ({len(allwin)}): {allwin}")
    json.dump(results, open("outputs/experiments_paper/per_asset_wf.json", "w"), indent=2)


if __name__ == "__main__":
    main()
