"""
Factor evolution loop (generate -> static-check -> walk-forward IC/IR ->
de-correlate -> admit). Produces docs/best_factor_evolved.json.

Pipeline:
  1. Seed from existing high-IR expressions in docs/best_factor.json.
  2. Generate candidates: operator wrapping, window perturbation, binary recombine.
  3. Static check: DSL evaluates to a finite, non-constant series on US data.
  4. Walk-forward IC/IR on the TRAIN window (causal; DSL TS_ ops use only past).
  5. De-correlate: reject if |corr| > 0.9 with any admitted/seed factor.
  6. Admit if |IR_train| >= threshold.

Usage:
  python scripts/evolve_factors.py --rounds 3 --admit-ir 0.6 --max-new 40
"""
import sys, json, argparse, random, warnings
import numpy as np
import pandas as pd
from pathlib import Path
warnings.filterwarnings("ignore")

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from finvl.factors.dsl_engine import FactorDSL

DATA_PATH = "data/processed/us_dow30.csv"
TRAIN_START, TRAIN_END = "2019-01-01", "2023-12-31"
SEED_FILE = "docs/best_factor.json"
OUT_FILE = "docs/best_factor_evolved.json"
WINDOWS = [3, 5, 6, 7, 9, 10, 20, 30, 60]
UNARY = ["TS_ZSCORE({e},{w})", "TS_RANK({e},{w})", "DELTA({e},{w})",
         "TS_MEAN({e},{w})", "RANK({e})"]


def load_train_panel():
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


def load_seeds():
    seeds = []
    for l in open(SEED_FILE):
        l = l.strip()
        if not l or l == "null":
            continue
        try:
            d = json.loads(l)
        except Exception:
            continue
        if d and d.get("expr") and d.get("name"):
            seeds.append({"name": d["name"], "expr": d["expr"],
                          "ir": float(d.get("Information_Ratio_with_cost", 0))})
    return seeds


def perturb_window(expr):
    import re
    nums = re.findall(r'\d+', expr)
    if not nums:
        return None
    old = random.choice([n for n in nums if int(n) in WINDOWS] or nums)
    new = str(random.choice(WINDOWS))
    return expr.replace(old, new, 1) if new != old else None


def gen_candidates(seeds, n):
    cands = []
    exprs = [s["expr"] for s in seeds]
    for _ in range(n):
        mode = random.random()
        if mode < 0.4:
            e = random.choice(exprs); tmpl = random.choice(UNARY); w = random.choice(WINDOWS)
            cands.append(tmpl.format(e=f"({e})", w=w))
        elif mode < 0.7:
            e = perturb_window(random.choice(exprs))
            if e: cands.append(e)
        else:
            a, b = random.sample(exprs, 2); op = random.choice([" + ", " - ", " * "])
            cands.append(f"({a}){op}({b})")
    return list(dict.fromkeys(cands))


def factor_ir(dsl, expr, panel):
    ics = []; series_cache = []
    for t, g in panel.items():
        try:
            sig = dsl.evaluate(expr, g).values.astype(float)
        except Exception:
            return None, None
        close = g['close'].values.astype(float)
        if len(sig) != len(close) or len(close) < 60:
            continue
        fwd = np.concatenate([np.diff(close) / close[:-1], [np.nan]])
        s = sig[:-1]; r = fwd[:-1]
        m = np.isfinite(s) & np.isfinite(r)
        if m.sum() < 60 or np.std(s[m]) < 1e-9:
            continue
        c = np.corrcoef(s[m], r[m])[0, 1]
        if np.isfinite(c):
            ics.append(c); series_cache.append(sig)
    if len(ics) < 5:
        return None, None
    ic = np.mean(ics); ir = ic / (np.std(ics) + 1e-9) * np.sqrt(len(ics))
    return ir, np.concatenate(series_cache) if series_cache else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=2)
    ap.add_argument("--admit-ir", type=float, default=0.6, dest="admit_ir")
    ap.add_argument("--max-new", type=int, default=40, dest="max_new")
    ap.add_argument("--per-round", type=int, default=120, dest="per_round")
    ap.add_argument("--corr-max", type=float, default=0.9, dest="corr_max")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    random.seed(args.seed); np.random.seed(args.seed)

    dsl = FactorDSL(); panel = load_train_panel(); seeds = load_seeds()
    print(f"Loaded {len(seeds)} seed factors, {len(panel)} train tickers")
    admitted = []; ref_sigs = []
    for s in sorted(seeds, key=lambda x: -x["ir"])[:30]:
        ir, sig = factor_ir(dsl, s["expr"], panel)
        if sig is not None:
            ref_sigs.append(sig)
    new_factors = []
    for rd in range(1, args.rounds + 1):
        cands = gen_candidates(seeds + admitted, args.per_round)
        admitted_this = 0
        for expr in cands:
            if len(new_factors) >= args.max_new:
                break
            ir, sig = factor_ir(dsl, expr, panel)
            if ir is None or abs(ir) < args.admit_ir or sig is None:
                continue
            dup = False; L = len(sig)
            for rs in ref_sigs:
                m = min(L, len(rs)); a, b = sig[:m], rs[:m]
                mm = np.isfinite(a) & np.isfinite(b)
                if mm.sum() > 50 and np.std(a[mm]) > 1e-9 and np.std(b[mm]) > 1e-9:
                    if abs(np.corrcoef(a[mm], b[mm])[0, 1]) > args.corr_max:
                        dup = True; break
            if dup:
                continue
            name = f"EVO_{args.seed}_{rd}_{len(new_factors):03d}"
            new_factors.append({"name": name, "expr": expr,
                                 "Information_Ratio_with_cost": round(abs(ir), 3),
                                 "category": "evolved_us", "round": rd})
            ref_sigs.append(sig); admitted_this += 1
        print(f"Round {rd}: +{admitted_this} admitted (total new {len(new_factors)})")
        if len(new_factors) >= args.max_new:
            break
    with open(OUT_FILE, "w") as f:
        for s in seeds:
            f.write(json.dumps({"name": s["name"], "expr": s["expr"],
                                "Information_Ratio_with_cost": s["ir"]}) + "\n")
        for nf in new_factors:
            f.write(json.dumps(nf) + "\n")
    print(f"Wrote {len(seeds)+len(new_factors)} factors -> {OUT_FILE}")


if __name__ == "__main__":
    main()
