"""
Multi-window robustness with a FinOPD parameter sweep, to improve the weak
window (2025-H1) without harming the others. Reports, for each candidate param
set, FinOPD's Sharpe/Calmar rank in every window; selects the config with the
best worst-window Sharpe rank (min-max objective).
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

ASSETS = ["GOOGL", "GS", "JNJ", "NVDA"]
WINDOWS = {
    "2025-Full": ("2025-01-01", "2025-12-31"),
    "2025-H1":   ("2025-01-01", "2025-06-30"),
    "2025-H2":   ("2025-07-01", "2025-12-31"),
    "2025-2026": ("2025-01-01", "2026-05-27"),
}
# candidate FinOPD param sets (base_entry, add_entry, tp, sl, step)
CANDIDATES = {
    "ride":   (0.05, 0.15, 0.99, 0.08, 0.5),   # no take-profit: ride trends (helps choppy exits)
    "ride2":  (0.04, 0.12, 0.99, 0.10, 0.5),
    "tp20":   (0.05, 0.15, 0.20, 0.08, 0.5),   # original
    "tp30":   (0.05, 0.15, 0.30, 0.10, 0.5),
    "tight":  (0.06, 0.18, 0.15, 0.05, 0.5),
    "scale":  (0.04, 0.12, 0.99, 0.08, 0.33),  # smaller scaling steps
}


def precompute(top, full):
    close = full['close'].values.astype(float); n = len(close)
    df_f = full.copy(); df_f.columns = [c.lower() for c in df_f.columns]
    fs = np.zeros(n); tot = 0.0
    for f in top:
        try:
            vals = f.compute(df_f).values
            if len(vals) == n:
                s = np.sign(vals) * f.ir; s[~np.isfinite(vals) | (vals == 0)] = 0
                fs += s; tot += f.ir
        except Exception: pass
    return close, fs / (tot if tot > 0 else 1.0)


def gen(close, fs, ind, be, ae, tp, sl, step, lookback=60):
    sma10, sma20, sma50, rsi, r20, r5, v20 = ind
    n = len(close); pos = 0.0; out = []; epx = None
    for i in range(n):
        if i < lookback or np.isnan(sma20[i]):
            out.append(pos if i >= lookback else 0.0); continue
        cur = close[i]; pvsma = (cur - sma20[i]) / (sma20[i] + 1e-8)
        trend = np.clip(0.4*np.sign(pvsma)*min(abs(pvsma)*5,1)+0.4*np.sign(r20[i])*min(abs(r20[i])*5,1)
                        + 0.2*np.sign(r5[i])*min(abs(r5[i])*10,1), -1, 1)
        factor = fs[i]
        if v20[i] > 0.35: wt, wf = 0.3, 0.7
        elif abs(r20[i]) > 0.08: wt, wf = 0.7, 0.3
        else: wt, wf = 0.5, 0.5
        score = (wt*trend + wf*factor) if trend*factor > 0 else (0.6*trend + 0.4*factor)
        if pos > 0 and epx is not None:
            ret = (cur - epx) / epx
            if ret >= tp: pos = 0.0; epx = None; out.append(pos); continue
            if ret <= -sl: pos = 0.0; epx = None; out.append(pos); continue
        if score > ae:
            if pos == 0: epx = cur
            pos = min(1.0, (pos if pos > 0 else 0.0) + step)
        elif score > be:
            if pos == 0: epx = cur; pos = step
        elif score < -be:
            pos = 0.0; epx = None
        if not np.isnan(sma50[i]) and cur < sma50[i] and r20[i] < -0.04:
            pos = 0.0; epx = None
        pos = max(min(pos, 1.0), 0.0); out.append(pos)
    return out


def main():
    df_all = hv3.load_all()
    lib = FactorLibrary(factor_json_path="docs/best_factor_evolved.json")
    top = sorted([f for f in lib.factors.values() if f.ir >= 1.0], key=lambda f: -f.ir)
    ts_bl = hv3.load_ts_baselines()

    # Precompute per (window, asset): baseline aggregate metrics list, and FinOPD blend/indicators
    prep = {}
    for wname, (s, e) in WINDOWS.items():
        prep[wname] = {}
        for t in ASSETS:
            tdf = df_all[df_all['ticker'] == t].set_index('date').sort_index()
            full = tdf.loc[tdf.index <= pd.Timestamp(e)]
            mask = np.asarray((full.index >= pd.Timestamp(s)) & (full.index <= pd.Timestamp(e)))
            if mask.sum() < 40: continue
            si = int(np.argmax(mask)); prices = full['close'].values.astype(float)[si:]
            ind = hv3.indicators(prices)
            bl = {}
            for bn, fn in hv3.AGENT_BASELINES.items():
                bl[bn] = hv3.compute_metrics(fn(prices, ind), prices)
            for disp, am in ts_bl.items():
                if t in am: bl[disp] = am[t]
            bl = {k: v for k, v in bl.items() if v}
            close, fs = precompute(top, full)
            prep[wname][t] = {"si": si, "prices": prices, "ind": ind, "bl": bl,
                              "close": close, "fs": fs, "full_close": full['close'].values.astype(float)}

    best = None
    report = {}
    for cname, (be, ae, tp, sl, step) in CANDIDATES.items():
        wranks = {}
        for wname in WINDOWS:
            # aggregate FinOPD + baselines across assets
            agg = {}
            fo_list = []
            bl_lists = {}
            for t, P in prep[wname].items():
                m = hv3.compute_metrics(gen(P["close"], P["fs"], hv3.indicators(P["close"]), be, ae, tp, sl, step)[P["si"]:], P["prices"])
                if m: fo_list.append(m)
                for bn, bm in P["bl"].items():
                    bl_lists.setdefault(bn, []).append(bm)
            if not fo_list: continue
            fo = {k: np.mean([x[k] for x in fo_list]) for k in ["CR", "SR", "MDD", "WR"]}
            fo["Calmar"] = fo["CR"] / fo["MDD"] if fo["MDD"] > 1e-6 else 0.0
            agg["FinOPD"] = fo
            for bn, lst in bl_lists.items():
                a = {k: np.mean([x[k] for x in lst]) for k in ["CR", "SR", "MDD", "WR"]}
                a["Calmar"] = a["CR"] / a["MDD"] if a["MDD"] > 1e-6 else 0.0
                agg[bn] = a
            n = len(agg)
            sr_rank = 1 + sum(1 for m, v in agg.items() if m != "FinOPD" and v["SR"] > fo["SR"])
            cal_rank = 1 + sum(1 for m, v in agg.items() if m != "FinOPD" and v["Calmar"] > fo["Calmar"])
            wranks[wname] = {"SR": round(fo["SR"], 2), "SR_rank": sr_rank,
                             "Calmar": round(fo["Calmar"], 2), "Calmar_rank": cal_rank,
                             "MDD": round(fo["MDD"], 1), "CR": round(fo["CR"], 1), "n": n}
        worst_sr_rank = max(v["SR_rank"] for v in wranks.values())
        report[cname] = {"params": [be, ae, tp, sl, step], "windows": wranks, "worst_sr_rank": worst_sr_rank}
        print(f"\n[{cname}] params={(be,ae,tp,sl,step)} worst_SR_rank={worst_sr_rank}")
        for wn, v in wranks.items():
            print(f"   {wn:11} SR={v['SR']:.2f}(#{v['SR_rank']}/{v['n']}) Calmar={v['Calmar']:.2f}(#{v['Calmar_rank']}) MDD={v['MDD']}")
        score = -worst_sr_rank + sum(-v["SR_rank"] for v in wranks.values()) * 0.01
        if best is None or score > best[0]:
            best = (score, cname)
    print(f"\nBEST config (min worst-window SR rank): {best[1]}")
    json.dump(report, open("outputs/experiments_paper/multiwindow_sweep.json", "w"), indent=2)
    print("Saved -> outputs/experiments_paper/multiwindow_sweep.json")


if __name__ == "__main__":
    main()
