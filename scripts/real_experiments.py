"""
Real component ablation + counterfactual + sensitivity for the multi-trade FinOPD,
under the unified v3 setting (4 showcase assets, full-year 2025, identical cost model).

Every variant toggles an ACTUAL implemented component and re-runs the deterministic
backtest, so the reported portfolio metrics are real (not illustrative).

Outputs:
  outputs/experiments_paper/real_ablation.json
  outputs/experiments_paper/real_counterfactual.json
  outputs/experiments_paper/real_sensitivity.json
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


def make_positions(close, fs, ind, cfg):
    """Configurable FinOPD position generator. cfg toggles components:
       use_rasw, use_ega, use_factor, use_trend_guard, tp, sl, base_entry, add_entry, step,
       single_trade (no scaling), factor_perturb in {None,'zero','shuffle'}."""
    sma10, sma20, sma50, rsi, r20, r5, v20 = ind
    n = len(close); pos = 0.0; out = []; epx = None
    fsig = fs.copy()
    if cfg.get("factor_perturb") == "zero":
        fsig = np.zeros(n)
    elif cfg.get("factor_perturb") == "shuffle":
        rng = np.random.RandomState(42); fsig = fsig.copy(); rng.shuffle(fsig)
    be, ae = cfg.get("base_entry", 0.05), cfg.get("add_entry", 0.15)
    tp, sl, step = cfg.get("tp", 0.99), cfg.get("sl", 0.08), cfg.get("step", 0.5)
    lookback = 60
    for i in range(n):
        if i < lookback or np.isnan(sma20[i]):
            out.append(pos if i >= lookback else 0.0); continue
        cur = close[i]; pvsma = (cur - sma20[i]) / (sma20[i] + 1e-8)
        trend = np.clip(0.4*np.sign(pvsma)*min(abs(pvsma)*5,1)+0.4*np.sign(r20[i])*min(abs(r20[i])*5,1)
                        + 0.2*np.sign(r5[i])*min(abs(r5[i])*10,1), -1, 1)
        factor = fsig[i] if cfg.get("use_factor", True) else 0.0
        if cfg.get("use_rasw", True):
            if v20[i] > 0.35: wt, wf = 0.3, 0.7
            elif abs(r20[i]) > 0.08: wt, wf = 0.7, 0.3
            else: wt, wf = 0.5, 0.5
        else:
            wt, wf = 0.5, 0.5  # fixed weights
        score = (wt*trend + wf*factor) if trend*factor > 0 else (0.6*trend + 0.4*factor)
        if pos > 0 and epx is not None:
            ret = (cur - epx) / epx
            if ret >= tp: pos = 0.0; epx = None; out.append(pos); continue
            if ret <= -sl: pos = 0.0; epx = None; out.append(pos); continue
        if cfg.get("use_ega", True):
            if score > ae:
                if pos == 0: epx = cur
                pos = min(1.0, (pos if pos > 0 else 0.0) + (1.0 if cfg.get("single_trade") else step))
            elif score > be:
                if pos == 0: epx = cur; pos = (1.0 if cfg.get("single_trade") else step)
            elif score < -be:
                pos = 0.0; epx = None
        else:
            # no edge gating: always take a directional position by sign of score
            if score > 0:
                if pos == 0: epx = cur
                pos = 1.0
            else:
                pos = 0.0; epx = None
        if cfg.get("use_trend_guard", True) and not np.isnan(sma50[i]) and cur < sma50[i] and r20[i] < -0.04:
            pos = 0.0; epx = None
        pos = max(min(pos, 1.0), 0.0); out.append(pos)
    return out


def portfolio(df_all, top, cfg):
    mets = []
    for t in ASSETS:
        tdf = df_all[df_all['ticker'] == t].set_index('date').sort_index()
        full = tdf.loc[tdf.index <= pd.Timestamp(END)]
        mask = np.asarray((full.index >= pd.Timestamp(START)) & (full.index <= pd.Timestamp(END)))
        if mask.sum() < 60: continue
        si = int(np.argmax(mask)); prices = full['close'].values.astype(float)[si:]
        fin = hv3.FinOPDMulti(top); close, fs = fin.blend(full)
        ind = hv3.indicators(close)
        m = hv3.compute_metrics(make_positions(close, fs, ind, cfg)[si:], prices)
        if m: mets.append(m)
    if not mets: return None
    agg = {k: round(float(np.mean([x[k] for x in mets])), 2) for k in ["CR", "SR", "MDD", "WR"]}
    agg["Calmar"] = round(agg["CR"] / agg["MDD"], 2) if agg["MDD"] > 1e-6 else 0.0
    agg["n_trades"] = round(float(np.mean([x["n_trades"] for x in mets])), 1)
    return agg


def main():
    df_all = hv3.load_all()
    lib = FactorLibrary(factor_json_path="docs/best_factor_evolved.json")
    top = sorted([f for f in lib.factors.values() if f.ir >= 1.0], key=lambda f: -f.ir)
    base = dict(use_rasw=True, use_ega=True, use_factor=True, use_trend_guard=True,
               tp=0.99, sl=0.08, base_entry=0.05, add_entry=0.15, step=0.5)

    # ---- Ablation ----
    full_m = portfolio(df_all, top, base)
    ablation = {"A1_full": full_m}
    variants = {
        "A2_no_factor":      {**base, "use_factor": False},
        "A4_no_rasw":        {**base, "use_rasw": False},
        "A7_no_trend_guard": {**base, "use_trend_guard": False},
        "A8_single_trade":   {**base, "single_trade": True},
        "A10_no_ega":        {**base, "use_ega": False},
    }
    for name, cfg in variants.items():
        m = portfolio(df_all, top, cfg)
        if m and full_m:
            m["dSR"] = round(m["SR"] - full_m["SR"], 2)
        ablation[name] = m
    json.dump(ablation, open("outputs/experiments_paper/real_ablation.json", "w"), indent=2)
    print("=== ABLATION ===")
    for k, v in ablation.items():
        print(f"  {k:20} SR={v['SR']:.2f} MDD={v['MDD']:.1f} CR={v['CR']:.1f} WR={v['WR']:.1f} dSR={v.get('dSR','-')}")

    # ---- Counterfactual (factor-signal perturbations) ----
    cf = {"intact": full_m}
    for name, pert in [("factor_zero", "zero"), ("factor_shuffle", "shuffle")]:
        m = portfolio(df_all, top, {**base, "factor_perturb": pert})
        if m and full_m: m["dSR"] = round(m["SR"] - full_m["SR"], 2)
        cf[name] = m
    # no-trend-guard already a structural perturbation
    json.dump(cf, open("outputs/experiments_paper/real_counterfactual.json", "w"), indent=2)
    print("=== COUNTERFACTUAL ===")
    for k, v in cf.items():
        print(f"  {k:16} SR={v['SR']:.2f} dSR={v.get('dSR','-')}")

    # ---- Sensitivity ----
    sens = {}
    for tp in [0.10, 0.15, 0.20, 0.30, 0.99]:
        sens[f"tp_{tp}"] = portfolio(df_all, top, {**base, "tp": tp})
    for sl in [0.04, 0.06, 0.08, 0.12, 0.20]:
        sens[f"sl_{sl}"] = portfolio(df_all, top, {**base, "sl": sl})
    for be in [0.02, 0.05, 0.08, 0.12]:
        sens[f"entry_{be}"] = portfolio(df_all, top, {**base, "base_entry": be, "add_entry": be+0.10})
    json.dump(sens, open("outputs/experiments_paper/real_sensitivity.json", "w"), indent=2)
    print("=== SENSITIVITY ===")
    for k, v in sens.items():
        if v: print(f"  {k:14} SR={v['SR']:.2f} MDD={v['MDD']:.1f} CR={v['CR']:.1f}")
    print("\nSaved real_ablation/counterfactual/sensitivity.json")


if __name__ == "__main__":
    main()
