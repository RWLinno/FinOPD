"""
Out-of-sample (2025) validation of US-evolved cross-sectional factors.
Reads docs/best_factor_us.json (with explicit per-factor sign learned on
2019-2024), builds a signed IR-weighted composite, ranks the Dow universe daily,
goes long top-k (optionally short bottom-k), and compares to equal-weight and a
single-factor baseline under the identical cost model.

IMPORTANT: factor signs are fixed from the TRAIN window; 2025 is strictly OOS.

Usage:
  python scripts/xsection_us_eval.py --topk 6 --hold 5 --mode longshort
"""
import sys, json, argparse, warnings
import numpy as np, pandas as pd
from pathlib import Path
warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from finvl.factors.dsl_engine import FactorDSL

DATA_PATH = "data/processed/us_dow30.csv"
COST_RT, SLIPPAGE = 0.0015, 0.0005
TEST_START, TEST_END = "2025-01-01", "2025-12-31"
US_FACTORS = "docs/best_factor_us.json"


def load_panel():
    df = pd.read_csv(DATA_PATH)
    df.columns = [c.lower().replace(' ', '_') for c in df.columns]
    df['date'] = pd.to_datetime(df['date'])
    return df.sort_values(['ticker', 'date'])


def load_us_factors(min_icir):
    fs = []
    for l in open(US_FACTORS):
        l = l.strip()
        if not l:
            continue
        d = json.loads(l)
        if abs(d.get("cs_icir", 0)) >= min_icir:
            fs.append((d["expr"], d.get("sign", 1.0), abs(d.get("cs_icir", 1.0))))
    return fs


def build_signed_scores(df, dsl, factors):
    """Composite signed z-scored factor per [date x ticker]."""
    per_ticker = {}
    for t, g in df.groupby('ticker'):
        g = g.sort_values('date').set_index('date')
        if len(g) < 80:
            continue
        gf = g.copy(); gf.columns = [c.lower() for c in gf.columns]
        n = len(g); comp = np.zeros(n); tot = 0.0
        for expr, sign, w in factors:
            try:
                v = dsl.evaluate(expr, gf).values.astype(float)
                if len(v) != n:
                    continue
                s = pd.Series(v)
                z = ((s - s.rolling(60, min_periods=20).mean()) / s.rolling(60, min_periods=20).std()).fillna(0).values
                comp += sign * np.clip(z, -3, 3) * w
                tot += w
            except Exception:
                continue
        comp /= (tot if tot > 0 else 1.0)
        per_ticker[t] = pd.Series(comp, index=g.index)
    return pd.DataFrame(per_ticker)


def metrics(pr):
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
            "MDD": round(mdd, 2), "Calmar": round(cr / mdd, 2) if mdd > 1e-9 else 0.0}


def run_portfolio(scores, ret, px, topk, hold, mode):
    dates = [d for d in scores.index if pd.Timestamp(TEST_START) <= d <= pd.Timestamp(TEST_END)]
    weights = pd.DataFrame(0.0, index=px.index, columns=px.columns)
    last_w = pd.Series(0.0, index=px.columns); rebal = set(dates[::hold])
    for d in dates:
        if d in rebal:
            s = scores.loc[d].dropna(); s = s[s.index.isin(px.columns)]
            if len(s) >= 2 * topk:
                ranked = s.sort_values(); w = pd.Series(0.0, index=px.columns)
                w[ranked.index[-topk:]] = 1.0 / topk
                if mode == "longshort":
                    w[ranked.index[:topk]] = -1.0 / topk
                last_w = w
        weights.loc[d] = last_w
    w_exec = weights.shift(1).fillna(0)
    gross = (w_exec * ret).loc[dates].sum(axis=1)
    turn = w_exec.diff().abs().loc[dates].sum(axis=1)
    pr = (gross - turn * (COST_RT / 2 + SLIPPAGE)).values
    return metrics(pr), float(turn.mean())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--topk", type=int, default=6)
    ap.add_argument("--hold", type=int, default=5)
    ap.add_argument("--mode", choices=["long", "longshort"], default="longshort")
    ap.add_argument("--min-icir", type=float, default=0.5, dest="min_icir")
    args = ap.parse_args()

    df = load_panel(); dsl = FactorDSL()
    factors = load_us_factors(args.min_icir)
    print(f"US factors used (|ICIR|>={args.min_icir}): {len(factors)} | mode={args.mode} topk={args.topk} hold={args.hold}")
    px = df.pivot(index='date', columns='ticker', values='close').sort_index()
    ret = px.pct_change().fillna(0)
    scores = build_signed_scores(df, dsl, factors)

    fin, turn = run_portfolio(scores, ret, px, args.topk, args.hold, args.mode)
    tdates = [d for d in ret.index if pd.Timestamp(TEST_START) <= d <= pd.Timestamp(TEST_END)]
    ew = metrics(ret.loc[tdates].mean(axis=1).values)

    print("\n=== 2025 OUT-OF-SAMPLE cross-sectional results ===")
    print(f"  Equal-Weight universe : SR={ew['SR']:.2f} CR={ew['CR']:.1f} MDD={ew['MDD']:.1f} Cal={ew['Calmar']:.2f} Sortino={ew['Sortino']:.2f}")
    if fin:
        flag = "  <== beats equal-weight" if fin["SR"] > ew["SR"] else ""
        print(f"  FinOPD US X-sectional : SR={fin['SR']:.2f} CR={fin['CR']:.1f} MDD={fin['MDD']:.1f} Cal={fin['Calmar']:.2f} Sortino={fin['Sortino']:.2f} turn={turn:.3f}{flag}")
    json.dump({"finopd_us_xs": fin, "equal_weight": ew, "config": vars(args), "turnover": turn},
              open("outputs/experiments_paper/xsection_us.json", "w"), indent=2)


if __name__ == "__main__":
    main()
