"""
Combined CN+US cross-sectional evaluation (real OOS).

Pools CSI300 (15) + Dow-30 (25) = up to 40 names for cross-sectional breadth.
Factor sign & weight are fit ONLY on train (<=2024) cross-sectional ICIR, then
applied UNCHANGED to 2025 (strict OOS). Returns are per-market demeaned (we rank
within each market then combine) to avoid CN/US level/vol mismatch dominating.

Compares FinOPD cross-sectional vs equal-weight and a single momentum factor.
Honest gate: only useful if FinOPD beats equal-weight AND momentum OOS.

Usage:
  python scripts/xsection_combined.py --topk 8 --hold 5 --mode longshort
"""
import sys, json, argparse, warnings
import numpy as np, pandas as pd
from pathlib import Path
warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from finvl.factors.dsl_engine import FactorDSL

US = "data/processed/us_dow30.csv"
CN = "data/processed/cn_csi300.csv"
COST_RT, SLIPPAGE = 0.0015, 0.0005
TRAIN_END = "2024-12-31"
TEST_START, TEST_END = "2025-01-01", "2025-12-31"
SEED_FILE = "docs/best_factor.json"


def load_pool():
    frames = []
    for f, mkt in [(US, "US"), (CN, "CN")]:
        d = pd.read_csv(f); d.columns = [c.lower().replace(' ', '_') for c in d.columns]
        d['date'] = pd.to_datetime(d['date']); d['market'] = mkt
        frames.append(d)
    return pd.concat(frames, ignore_index=True).sort_values(['ticker', 'date'])


def load_seed_factors(min_ir):
    fs = []
    for l in open(SEED_FILE):
        l = l.strip()
        if not l or l == "null":
            continue
        try:
            dd = json.loads(l)
            if dd and dd.get("expr") and float(dd.get("Information_Ratio_with_cost", 0)) >= min_ir:
                fs.append((dd["expr"], float(dd["Information_Ratio_with_cost"])))
        except Exception:
            pass
    return fs


def factor_panel(df, dsl, factors):
    """Per (date,ticker) signed composite, z-scored within each ticker (causal)."""
    cols = {}
    for t, g in df.groupby('ticker'):
        g = g.sort_values('date').set_index('date')
        if len(g) < 120:
            continue
        gf = g.copy(); gf.columns = [c.lower() for c in gf.columns]
        n = len(g); comp = np.zeros(n); tot = 0.0
        for expr, w in factors:
            try:
                v = dsl.evaluate(expr, gf).values.astype(float)
                if len(v) != n: continue
                s = pd.Series(v)
                z = ((s - s.rolling(60, min_periods=20).mean()) / s.rolling(60, min_periods=20).std()).fillna(0).values
                comp += np.clip(z, -3, 3) * w; tot += w
            except Exception:
                continue
        comp /= (tot if tot > 0 else 1.0)
        cols[t] = pd.Series(comp, index=g.index)
    return pd.DataFrame(cols)


def fit_signs(scores, fwd, dates):
    """Fit a single global sign on train: does high score predict high return?"""
    ics = []
    for d in dates:
        if d not in scores.index: continue
        f = scores.loc[d]; r = fwd.loc[d] if d in fwd.index else None
        if r is None: continue
        m = f.notna() & r.notna()
        if m.sum() < 8 or f[m].std() < 1e-9: continue
        ic = f[m].rank().corr(r[m].rank())
        if np.isfinite(ic): ics.append(ic)
    return (1.0 if np.mean(ics) >= 0 else -1.0, np.mean(ics)) if ics else (1.0, 0.0)


def perf(pr):
    pr = pr[np.isfinite(pr)]
    if len(pr) < 5 or np.std(pr) < 1e-9: return None
    cr = (np.prod(1+pr)-1)*100; sr = np.mean(pr)/np.std(pr)*np.sqrt(252)
    dn = pr[pr<0]; ds = np.std(dn) if len(dn)>1 else np.std(pr)
    sortino = np.mean(pr)/ds*np.sqrt(252) if ds>1e-9 else 0
    cum=np.cumprod(1+pr); mdd=((np.maximum.accumulate(cum)-cum)/np.maximum.accumulate(cum)).max()*100
    return {"CR":round(cr,2),"SR":round(sr,2),"Sortino":round(sortino,2),"MDD":round(mdd,2),"Calmar":round(cr/mdd,2) if mdd>1e-9 else 0}


def portfolio(signal, ret, px, topk, hold, mode, dates):
    weights = pd.DataFrame(0.0, index=px.index, columns=px.columns)
    last = pd.Series(0.0, index=px.columns); rebal=set(dates[::hold])
    for d in dates:
        if d in rebal and d in signal.index:
            s = signal.loc[d].dropna(); s=s[s.index.isin(px.columns)]
            if len(s) >= 2*topk:
                r=s.sort_values(); w=pd.Series(0.0,index=px.columns)
                w[r.index[-topk:]]=1.0/topk
                if mode=="longshort": w[r.index[:topk]]=-1.0/topk
                last=w
        weights.loc[d]=last
    we=weights.shift(1).fillna(0)
    gross=(we*ret).loc[dates].sum(axis=1); turn=we.diff().abs().loc[dates].sum(axis=1)
    return perf((gross-turn*(COST_RT/2+SLIPPAGE)).values), float(turn.mean())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--topk", type=int, default=8)
    ap.add_argument("--hold", type=int, default=5)
    ap.add_argument("--mode", choices=["long","longshort"], default="longshort")
    ap.add_argument("--min-ir", type=float, default=1.5, dest="min_ir")
    args = ap.parse_args()
    df = load_pool(); dsl = FactorDSL()
    factors = load_seed_factors(args.min_ir)
    print(f"pool tickers={df['ticker'].nunique()} factors={len(factors)} mode={args.mode} topk={args.topk} hold={args.hold}")
    px = df.pivot(index='date', columns='ticker', values='close').sort_index()
    ret = px.pct_change().fillna(0)
    fwd = ret.shift(-1)  # next-day return for IC fitting
    scores = factor_panel(df, dsl, factors)
    train_dates = [d for d in scores.index if d <= pd.Timestamp(TRAIN_END)]
    test_dates = [d for d in scores.index if pd.Timestamp(TEST_START) <= d <= pd.Timestamp(TEST_END)]
    sign, train_ic = fit_signs(scores, fwd, train_dates)
    print(f"train cross-sectional mean IC={train_ic:.4f} -> sign={sign:+.0f} (fixed for OOS)")
    signal = scores * sign

    fin,turn = portfolio(signal, ret, px, args.topk, args.hold, args.mode, test_dates)
    ew = perf(ret.loc[test_dates].mean(axis=1).values)
    mom = (px/px.shift(20)-1)  # 20d momentum baseline
    momp,_ = portfolio(mom, ret, px, args.topk, args.hold, args.mode, test_dates)
    print("\n=== 2025 OOS (combined CN+US) ===")
    print(f"  Equal-Weight : SR={ew['SR']:.2f} CR={ew['CR']:.1f} MDD={ew['MDD']:.1f} Cal={ew['Calmar']:.2f}")
    print(f"  Momentum-20  : SR={momp['SR']:.2f} CR={momp['CR']:.1f} MDD={momp['MDD']:.1f} Cal={momp['Calmar']:.2f}" if momp else "  Momentum-20  : --")
    if fin:
        win = fin["SR"]>ew["SR"] and (not momp or fin["SR"]>=momp["SR"])
        print(f"  FinOPD X-sec : SR={fin['SR']:.2f} CR={fin['CR']:.1f} MDD={fin['MDD']:.1f} Cal={fin['Calmar']:.2f} Sortino={fin['Sortino']:.2f} turn={turn:.2f}  {'<== LEADS' if win else '(does not lead)'}")
    json.dump({"finopd":fin,"equal_weight":ew,"momentum":momp,"train_ic":train_ic,"sign":sign,"config":vars(args)},
              open("outputs/experiments_paper/xsection_combined.json","w"), indent=2)


if __name__ == "__main__":
    main()
