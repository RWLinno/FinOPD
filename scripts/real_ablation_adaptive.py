"""
Real component ablation for the DEPLOYED regime-adaptive FinOPD (matches
eval_harness_v3.FinOPDMulti). Toggles each actual component and re-runs the
backtest on the 4 showcase assets (full-year 2025), reporting portfolio metrics.
Also reports the hindsight-teacher upper bound for reference.
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

ASSETS = ["GOOGL", "GS", "JNJ", "NVDA"]
START, END = "2025-01-01", "2025-12-31"


def positions(close, fs, ind, cfg):
    sma10, sma20, sma50, rsi, r20, r5, v20 = ind
    n = len(close); pos = 0.0; out = []; last = -999
    fsig = np.zeros(n) if not cfg.get("use_factor", True) else fs
    for i in range(n):
        if i < 60 or np.isnan(sma20[i]):
            out.append(0.0); continue
        cur = close[i]; pvsma = (cur - sma20[i]) / (sma20[i] + 1e-8)
        trend = np.clip(0.4*np.sign(pvsma)*min(abs(pvsma)*5,1)+0.4*np.sign(r20[i])*min(abs(r20[i])*5,1)
                        + 0.2*np.sign(r5[i])*min(abs(r5[i])*10,1), -1, 1)
        factor = fsig[i]
        if cfg.get("use_rasw", True):
            if v20[i] > 0.35: wt, wf = 0.3, 0.7
            elif abs(r20[i]) > 0.08: wt, wf = 0.7, 0.3
            else: wt, wf = 0.5, 0.5
        else:
            wt, wf = 0.5, 0.5
        score = (wt*trend + wf*factor) if trend*factor > 0 else (0.6*trend + 0.4*factor)
        if cfg.get("adaptive", True):
            if v20[i] >= 0.40: hold = 10
            elif v20[i] <= 0.20: hold = 20
            else: hold = 15
        else:
            hold = 1  # daily rebalancing (no adaptive low-turnover)
        if i - last >= hold:
            if score > 0.05: pos = 1.0
            elif score < -0.05: pos = 0.0
            if cfg.get("use_guard", True) and not np.isnan(sma50[i]) and cur < sma50[i] and r20[i] < -0.04:
                pos = 0.0
            last = i
        out.append(max(min(pos, 1.0), 0.0))
    return out


def teacher(close, k=20):
    n = len(close); out = []
    for i in range(n):
        j = min(i + k, n - 1); out.append(1.0 if (close[j]-close[i])/close[i] > 0 else 0.0)
    return out


def port(df_all, top, cfg, teacher_mode=False):
    ms = []
    for t in ASSETS:
        tdf = df_all[df_all['ticker'] == t].set_index('date').sort_index()
        full = tdf.loc[tdf.index <= pd.Timestamp(END)]
        mask = np.asarray((full.index >= pd.Timestamp(START)) & (full.index <= pd.Timestamp(END)))
        if mask.sum() < 60: continue
        si = int(np.argmax(mask)); prices = full['close'].values.astype(float)[si:]
        fin = hv3.FinOPDMulti(top); close, fs = fin.blend(full); ind = hv3.indicators(close)
        p = teacher(prices) if teacher_mode else positions(close, fs, ind, cfg)[si:]
        m = hv3.compute_metrics(p, prices)
        if m: ms.append(m)
    if not ms: return None
    cr = np.mean([x["CR"] for x in ms]); sr = np.mean([x["SR"] for x in ms]); md = np.mean([x["MDD"] for x in ms])
    return {"SR": round(float(sr),2), "CR": round(float(cr),1), "MDD": round(float(md),1),
            "Calmar": round(float(cr/md),2) if md>1e-9 else 0, "nt": round(float(np.mean([x["n_trades"] for x in ms])),1)}


def main():
    df_all = hv3.load_all()
    lib = FactorLibrary(factor_json_path="docs/best_factor_evolved.json")
    top = sorted([f for f in lib.factors.values() if f.ir >= 1.0], key=lambda f: -f.ir)
    base = dict(use_factor=True, use_rasw=True, use_guard=True, adaptive=True)
    full = port(df_all, top, base); tea = port(df_all, top, base, teacher_mode=True)
    variants = {
        "A2_no_factor": {**base, "use_factor": False},
        "A4_no_rasw": {**base, "use_rasw": False},
        "A7_no_guard": {**base, "use_guard": False},
        "A9_no_adaptive": {**base, "adaptive": False},
    }
    out = {"A1_full": full, "teacher": tea}
    print(f"A1_full       SR={full['SR']} MDD={full['MDD']} Cal={full['Calmar']} nt={full['nt']}")
    print(f"teacher(ub)   SR={tea['SR']} MDD={tea['MDD']} Cal={tea['Calmar']}")
    for nm, cfg in variants.items():
        m = port(df_all, top, cfg)
        if m: m["dSR"] = round(m["SR"]-full["SR"], 2)
        out[nm] = m
        print(f"{nm:14} SR={m['SR']} dSR={m['dSR']} MDD={m['MDD']} Cal={m['Calmar']} nt={m['nt']}")
    json.dump(out, open("outputs/experiments_paper/real_ablation.json", "w"), indent=2)


if __name__ == "__main__":
    main()
