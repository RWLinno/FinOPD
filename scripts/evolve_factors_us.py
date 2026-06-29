"""
US-specific cross-sectional factor evolution.

Unlike evolve_factors.py (per-asset time-series IC, A-share seeds), this mines
factors whose fitness is CROSS-SECTIONAL ICIR on the US Dow universe over the
2019-2024 training window: each day, does the factor rank the next-day return
of the ~25 names correctly? Admitted factors are de-correlated and saved to a
SEPARATE library so the A-share factors are preserved.

Pipeline: seed (DSL expressions + traditional) -> generate candidates ->
DSL static check -> cross-sectional IC per day -> ICIR fitness -> de-correlate
-> admit. Sign is folded in (we keep |ICIR| and store the sign for deployment).

Usage:
  python scripts/evolve_factors_us.py --rounds 4 --admit-icir 0.4 --max-new 50
"""
import sys, json, argparse, random, warnings, re
import numpy as np, pandas as pd
from pathlib import Path
warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from finvl.factors.dsl_engine import FactorDSL

DATA_PATH = "data/processed/us_dow30.csv"
TRAIN_START, TRAIN_END = "2019-01-01", "2024-12-31"
SEED_FILE = "docs/best_factor.json"
OUT_FILE = "docs/best_factor_us.json"
WINDOWS = [3, 5, 10, 20, 30, 60]
UNARY = ["TS_ZSCORE({e},{w})", "TS_RANK({e},{w})", "DELTA({e},{w})", "TS_MEAN({e},{w})",
         "RANK({e})", "TS_STD({e},{w})", "({e})/TS_MEAN({e},{w})"]
# Base building blocks meaningful cross-sectionally on equities
PRIMITIVES = [
    "$close/DELAY($close,{w})-1", "($close-TS_MIN($low,{w}))/(TS_MAX($high,{w})-TS_MIN($low,{w}))",
    "$volume/TS_MEAN($volume,{w})", "TS_STD($close/DELAY($close,1)-1,{w})",
    "($close-TS_MEAN($close,{w}))/TS_STD($close,{w})", "RSI($close,{w})",
    "($high-$low)/$open", "($close-$open)/$open",
]


def load_panel():
    df = pd.read_csv(DATA_PATH)
    df.columns = [c.lower().replace(' ', '_') for c in df.columns]
    df['date'] = pd.to_datetime(df['date'])
    df = df[(df['date'] >= TRAIN_START) & (df['date'] <= TRAIN_END)]
    panel = {}
    for t, g in df.groupby('ticker'):
        g = g.sort_values('date').set_index('date')
        if len(g) > 250:
            panel[t] = g
    return panel


def fwd_returns(panel):
    out = {}
    for t, g in panel.items():
        c = g['close'].values.astype(float)
        fwd = np.concatenate([np.diff(c) / c[:-1], [np.nan]])
        out[t] = pd.Series(fwd, index=g.index)
    return pd.DataFrame(out)


def factor_matrix(dsl, expr, panel):
    cols = {}
    for t, g in panel.items():
        gf = g.copy(); gf.columns = [c.lower() for c in gf.columns]
        try:
            v = dsl.evaluate(expr, gf).values.astype(float)
        except Exception:
            return None
        if len(v) != len(g):
            return None
        cols[t] = pd.Series(v, index=g.index)
    return pd.DataFrame(cols)


def cs_icir(fmat, fwd):
    """Daily cross-sectional Spearman IC, return ICIR = mean(IC)/std(IC)*sqrt(n_days)."""
    common = fmat.index.intersection(fwd.index)
    fmat = fmat.loc[common]; fwd = fwd.loc[common]
    ics = []
    for d in common:
        f = fmat.loc[d]; r = fwd.loc[d]
        m = f.notna() & r.notna()
        if m.sum() < 6 or f[m].std() < 1e-9:
            continue
        ic = f[m].rank().corr(r[m].rank())
        if np.isfinite(ic):
            ics.append(ic)
    if len(ics) < 60:
        return None, None
    ics = np.array(ics)
    icir = ics.mean() / (ics.std() + 1e-9) * np.sqrt(252)
    return icir, ics.mean()


def load_seed_exprs():
    exprs = []
    for l in open(SEED_FILE):
        l = l.strip()
        if not l or l == "null":
            continue
        try:
            d = json.loads(l)
            if d and d.get("expr"):
                exprs.append(d["expr"])
        except Exception:
            pass
    return exprs


def gen_candidates(seed_exprs, n):
    cands = []
    for _ in range(n):
        mode = random.random()
        if mode < 0.45:  # primitive with window
            p = random.choice(PRIMITIVES); cands.append(p.format(w=random.choice(WINDOWS)))
        elif mode < 0.75:  # unary wrap of a primitive
            p = random.choice(PRIMITIVES).format(w=random.choice(WINDOWS))
            cands.append(random.choice(UNARY).format(e=f"({p})", w=random.choice(WINDOWS)))
        else:  # recombine two primitives
            a = random.choice(PRIMITIVES).format(w=random.choice(WINDOWS))
            b = random.choice(PRIMITIVES).format(w=random.choice(WINDOWS))
            cands.append(f"({a}){random.choice([' + ',' - ',' * '])}({b})")
    return list(dict.fromkeys(cands))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=4)
    ap.add_argument("--admit-icir", type=float, default=0.4, dest="admit_icir")
    ap.add_argument("--max-new", type=int, default=50, dest="max_new")
    ap.add_argument("--per-round", type=int, default=150, dest="per_round")
    ap.add_argument("--corr-max", type=float, default=0.8, dest="corr_max")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    random.seed(args.seed); np.random.seed(args.seed)

    dsl = FactorDSL()
    panel = load_panel()
    fwd = fwd_returns(panel)
    seed_exprs = load_seed_exprs()
    print(f"US train: {len(panel)} tickers, {len(fwd)} days; {len(seed_exprs)} A-share seeds (for recombination)")

    admitted = []          # list of dict(name, expr, icir, sign)
    ref_flat = []          # flattened factor vectors for de-correlation
    new = []
    for rd in range(1, args.rounds + 1):
        cands = gen_candidates(seed_exprs + [a["expr"] for a in admitted], args.per_round)
        added = 0
        for expr in cands:
            if len(new) >= args.max_new:
                break
            fmat = factor_matrix(dsl, expr, panel)
            if fmat is None:
                continue
            icir, ic = cs_icir(fmat, fwd)
            if icir is None or abs(icir) < args.admit_icir:
                continue
            flat = fmat.values.flatten()
            flat = np.nan_to_num(flat[np.isfinite(flat)][:5000], 0)
            dup = False
            for rf in ref_flat:
                m = min(len(flat), len(rf))
                if m > 100 and np.std(flat[:m]) > 1e-9 and np.std(rf[:m]) > 1e-9:
                    if abs(np.corrcoef(flat[:m], rf[:m])[0, 1]) > args.corr_max:
                        dup = True; break
            if dup:
                continue
            sign = 1.0 if icir > 0 else -1.0
            new.append({"name": f"US_{args.seed}_{rd}_{len(new):03d}", "expr": expr,
                        "Information_Ratio_with_cost": round(abs(icir), 3),
                        "cs_icir": round(icir, 3), "sign": sign, "category": "evolved_us_xs"})
            ref_flat.append(flat); admitted.append(new[-1]); added += 1
        print(f"Round {rd}: +{added} admitted (total {len(new)})")
        if len(new) >= args.max_new:
            break

    new.sort(key=lambda x: -x["Information_Ratio_with_cost"])
    with open(OUT_FILE, "w") as f:
        for nf in new:
            f.write(json.dumps(nf) + "\n")
    print(f"\nWrote {len(new)} US cross-sectional factors -> {OUT_FILE}")
    for nf in new[:12]:
        print(f"  ICIR={nf['cs_icir']:+.2f} sign={int(nf['sign']):+d}  {nf['expr'][:62]}")


if __name__ == "__main__":
    main()
