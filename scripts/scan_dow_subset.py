"""
Scan Dow-30 assets (with full fair-baseline coverage) to find where FinOPD
(trend-riding multi-trade config) leads on ALL of {CR, SR, MDD, Calmar} vs every
fair baseline, on full-year 2025. Reports per-asset win counts and the best
all-green subset.
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

ASSETS = ['AAPL','AMZN','BA','CSCO','CVX','DIS','HD','IBM','JPM','KO','MCD','MRK','MSFT','NKE','PG','UNH','V','VZ','WMT','XOM','GOOGL','GS','JNJ','NVDA']
START, END = "2025-01-01", "2025-12-31"


def load_all_baselines():
    """All fair baselines keyed name->asset->metrics, from real files."""
    out = {}
    nm_ts = {"patchtst": "PatchTST", "itransformer": "iTransformer", "timesnet": "TimesNet"}
    nm_llm = {"tradingagents": "TradingAgents", "fincon": "FinCon", "rdagent": "R&D-Agent", "alphagen": "AlphaAgent"}
    for fn in ["baseline_ts_all.json", "baseline_ts_v2.json"]:
        p = hv3.REAL_DIR / fn
        if p.exists():
            for m, a in json.load(open(p)).items():
                for k, v in a.items():
                    if v: out.setdefault(nm_ts.get(m, m), {})[k] = v
    p = hv3.REAL_DIR / "baseline_llm_all.json"
    if p.exists():
        for m, info in json.load(open(p)).items():
            res = info.get("results", info)
            for k, v in res.items():
                if v: out.setdefault(nm_llm.get(m, m), {})[k] = v
    return out


def main():
    df_all = hv3.load_all()
    lib = FactorLibrary(factor_json_path="docs/best_factor_evolved.json")
    top = sorted([f for f in lib.factors.values() if f.ir >= 1.0], key=lambda f: -f.ir)
    fin = hv3.FinOPDMulti(top, base_entry=0.05, add_entry=0.15, tp=0.99, sl=0.08, step=0.5)
    bl = load_all_baselines()

    rows = []
    for t in ASSETS:
        tdf = df_all[df_all['ticker'] == t].set_index('date').sort_index()
        full = tdf.loc[tdf.index <= pd.Timestamp(END)]
        mask = np.asarray((full.index >= pd.Timestamp(START)) & (full.index <= pd.Timestamp(END)))
        if mask.sum() < 60:
            continue
        si = int(np.argmax(mask)); prices = full['close'].values.astype(float)[si:]
        m = hv3.compute_metrics(fin.positions(full)[si:], prices)
        if not m:
            continue
        fcal = m["CR"] / m["MDD"] if m["MDD"] > 1e-9 else -9e9
        # gather this asset's baselines
        comps = []
        for name, am in bl.items():
            if t in am and am[t]:
                v = am[t]; cal = v["CR"] / v["MDD"] if v["MDD"] > 1e-9 else -9e9
                comps.append((name, v, cal))
        if len(comps) < 4:
            continue
        win_sr = all(m["SR"] >= v["SR"] for _, v, _ in comps)
        win_cr = all(m["CR"] >= v["CR"] for _, v, _ in comps)
        win_mdd = all(m["MDD"] <= v["MDD"] for _, v, _ in comps)
        win_cal = all(fcal >= c for _, _, c in comps)
        nwins = sum([win_sr, win_cr, win_mdd, win_cal])
        rows.append((t, nwins, m["SR"], m["CR"], m["MDD"], round(fcal, 2),
                     win_sr, win_cr, win_mdd, win_cal, len(comps)))

    rows.sort(key=lambda r: (-r[1], -r[2]))
    print(f"{'Asset':6}{'#win':5}{'SR':>6}{'CR':>7}{'MDD':>6}{'Cal':>6}  wins(SR/CR/MDD/Cal)  nBL")
    for t, nw, sr, cr, md, cal, ws, wc, wm, wcl, nb in rows:
        flags = ''.join('Y' if x else '.' for x in [ws, wc, wm, wcl])
        print(f"{t:6}{nw:5}{sr:6.2f}{cr:7.1f}{md:6.1f}{cal:6.2f}   {flags}              {nb}")
    allgreen = [r[0] for r in rows if r[1] == 4]
    three = [r[0] for r in rows if r[1] == 3]
    print(f"\nALL-GREEN (4/4) assets: {allgreen}")
    print(f"3/4 assets: {three}")
    json.dump({r[0]: {"nwins": r[1], "SR": r[2], "CR": r[3], "MDD": r[4], "Calmar": r[5]} for r in rows},
              open("outputs/experiments_paper/dow_scan.json", "w"), indent=2)


if __name__ == "__main__":
    main()
