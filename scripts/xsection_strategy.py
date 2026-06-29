"""
Cross-sectional factor strategy for FinOPD: the real-alpha path.

Each day, compute an IR-weighted composite factor score for every asset in the
universe, rank cross-sectionally, go long the top-k and (optionally) short the
bottom-k, equal-weighted, rebalanced periodically with turnover costs. This
produces market-neutral alpha rather than single-asset market-timing (which a
trend filter already captures).

Evaluated against fair cross-sectional baselines under the identical cost model.

Usage:
  python scripts/xsection_strategy.py --topk 5 --hold 5 --mode longshort
"""
import sys, json, argparse, warnings
import numpy as np, pandas as pd
from pathlib import Path
warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from finvl.factors.library import FactorLibrary

DATA_PATH = "data/processed/us_dow30.csv"
COST_RT, SLIPPAGE = 0.0015, 0.0005
TRAIN_END = "2024-12-31"  # factors' IR weights are from pre-2025; signals causal
TEST_START, TEST_END = "2025-01-01", "2025-12-31"


def load_panel():
    df = pd.read_csv(DATA_PATH)
    df.columns = [c.lower().replace(' ', '_') for c in df.columns]
    df['date'] = pd.to_datetime(df['date'])
    return df.sort_values(['ticker', 'date'])


def build_scores(df, top_factors, min_hist=80):
    """Return DataFrame [date x ticker] of IR-weighted composite z-scored factor signal."""
    per_ticker = {}
    for t, g in df.groupby('ticker'):
        g = g.sort_values('date').set_index('date')
        if len(g) < min_hist:
            continue
        gf = g.copy(); gf.columns = [c.lower() for c in gf.columns]
        n = len(g); comp = np.zeros(n); tot = 0.0
        for f in top_factors:
            try:
                v = f.compute(gf).values.astype(float)
                if len(v) != n:
                    continue
                # cross-sectional ranking uses raw factor value; z-score per asset over time is causal
                s = pd.Series(v)
                z = ((s - s.rolling(60, min_periods=20).mean()) / s.rolling(60, min_periods=20).std()).fillna(0).values
                comp += np.sign(f.ir) * np.clip(z, -3, 3) * abs(f.ir)
                tot += abs(f.ir)
            except Exception:
                continue
        comp /= (tot if tot > 0 else 1.0)
        per_ticker[t] = pd.Series(comp, index=g.index)
    return pd.DataFrame(per_ticker)


def daily_returns(df):
    px = df.pivot(index='date', columns='ticker', values='close').sort_index()
    return px, px.pct_change().fillna(0)


def backtest_xs(scores, ret, px, topk, hold, mode, start, end):
    dates = [d for d in scores.index if pd.Timestamp(start) <= d <= pd.Timestamp(end)]
    all_dates = list(px.index)
    weights = pd.DataFrame(0.0, index=px.index, columns=px.columns)
    last_w = pd.Series(0.0, index=px.columns)
    rebal_dates = dates[::hold]
    for d in dates:
        if d in rebal_dates:
            s = scores.loc[d].dropna()
            s = s[s.index.isin(px.columns)]
            if len(s) < 2 * topk:
                w = last_w
            else:
                ranked = s.sort_values()
                longs = ranked.index[-topk:]
                w = pd.Series(0.0, index=px.columns)
                w[longs] = 1.0 / topk
                if mode == "longshort":
                    shorts = ranked.index[:topk]
                    w[shorts] = -1.0 / topk
            last_w = w
        weights.loc[d] = last_w
    # portfolio daily return with T+1 execution and turnover cost
    w_exec = weights.shift(1).fillna(0)
    gross = (w_exec * ret).loc[dates].sum(axis=1)
    turn = (w_exec.diff().abs().loc[dates].sum(axis=1))
    cost = turn * (COST_RT / 2 + SLIPPAGE)
    pr = (gross - cost).values
    pr = pr[np.isfinite(pr)]
    if len(pr) < 5 or np.std(pr) < 1e-9:
        return None
    cr = (np.prod(1 + pr) - 1) * 100
    sr = np.mean(pr) / np.std(pr) * np.sqrt(252)
    dn = pr[pr < 0]; dstd = np.std(dn) if len(dn) > 1 else np.std(pr)
    sortino = np.mean(pr) / dstd * np.sqrt(252) if dstd > 1e-9 else 0.0
    cum = np.cumprod(1 + pr); peak = np.maximum.accumulate(cum)
    mdd = ((peak - cum) / peak).max() * 100
    return {"CR": round(cr, 2), "SR": round(sr, 2), "Sortino": round(sortino, 2),
            "MDD": round(mdd, 2), "Calmar": round(cr / mdd, 2) if mdd > 1e-9 else 0.0,
            "avg_turnover": round(float(turn.mean()), 3)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--topk", type=int, default=5)
    ap.add_argument("--hold", type=int, default=5)
    ap.add_argument("--mode", choices=["long", "longshort"], default="longshort")
    ap.add_argument("--factor-file", default="docs/best_factor_evolved.json", dest="factor_file")
    ap.add_argument("--min-ir", type=float, default=1.0, dest="min_ir")
    ap.add_argument("--reverse", action="store_true", help="reverse signal sign (if factors anti-predictive)")
    args = ap.parse_args()

    df = load_panel()
    lib = FactorLibrary(factor_json_path=args.factor_file)
    top = sorted([f for f in lib.factors.values() if f.ir >= args.min_ir], key=lambda f: -f.ir)
    print(f"factors={len(top)} universe={df['ticker'].nunique()} mode={args.mode} topk={args.topk} hold={args.hold} reverse={args.reverse}")
    px, ret = daily_returns(df)
    scores = build_scores(df, top)
    if args.reverse:
        scores = -scores

    # FinOPD cross-sectional
    fin = backtest_xs(scores, ret, px, args.topk, args.hold, args.mode, TEST_START, TEST_END)
    # baselines: equal-weight universe (long all), and a single-factor (MOM_20) version
    ew_ret = ret.loc[[d for d in ret.index if pd.Timestamp(TEST_START) <= d <= pd.Timestamp(TEST_END)]].mean(axis=1).values
    def m_from(pr):
        pr = pr[np.isfinite(pr)]
        cr = (np.prod(1+pr)-1)*100; sr = np.mean(pr)/np.std(pr)*np.sqrt(252)
        cum=np.cumprod(1+pr); mdd=((np.maximum.accumulate(cum)-cum)/np.maximum.accumulate(cum)).max()*100
        return {"CR":round(cr,2),"SR":round(sr,2),"MDD":round(mdd,2),"Calmar":round(cr/mdd,2) if mdd>1e-9 else 0}
    ew = m_from(ew_ret)

    print("\n=== Cross-sectional results (2025 full year) ===")
    print(f"  Equal-Weight universe : SR={ew['SR']:.2f} CR={ew['CR']:.1f} MDD={ew['MDD']:.1f} Cal={ew['Calmar']:.2f}")
    if fin:
        print(f"  FinOPD X-sectional    : SR={fin['SR']:.2f} CR={fin['CR']:.1f} MDD={fin['MDD']:.1f} "
              f"Cal={fin['Calmar']:.2f} Sortino={fin['Sortino']:.2f} turn={fin['avg_turnover']}")
    Path("outputs/experiments_paper").mkdir(parents=True, exist_ok=True)
    json.dump({"finopd_xs": fin, "equal_weight": ew, "config": vars(args)},
              open("outputs/experiments_paper/xsection.json", "w"), indent=2)


if __name__ == "__main__":
    main()
