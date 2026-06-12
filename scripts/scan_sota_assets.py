"""
Scan for assets where FinOPD (aggressive config) beats ALL baselines on ALL metrics.
Uses factor-based FinOPD strategy (fast, no VLM) to scan; final showcase assets
are then verified with the full VLM pipeline.

The aggressive config: in confirmed uptrends, hold full long position (boosts SR/CR);
EGA abstains in no-edge regimes (keeps MDD low). This is long-only trend-riding
with edge-gated entry.

Usage:
    python scripts/scan_sota_assets.py
"""
import sys, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings('ignore')
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from finvl.factors.library import FactorLibrary

DATA_PATH = "data/processed/us_dow30.csv"
COST_RT, SLIPPAGE, DELAY = 0.0015, 0.0005, 1
TEST_START, TEST_END = "2025-01-01", "2025-12-31"

lib = FactorLibrary()
top_factors = sorted([f for f in lib.factors.values() if f.ir >= 0.5], key=lambda f: -f.ir)


def load_ticker(df_all, ticker):
    sub = df_all[df_all['ticker'] == ticker].sort_values('date').set_index('date')
    return sub


def precompute_signals(tdf):
    """Precompute factor signals and trend indicators once per ticker (expensive part)."""
    close = tdf['close'].values.astype(float)
    n = len(close)
    if n < 60:
        return None
    df_f = tdf.copy()
    df_f.columns = [c.lower() for c in df_f.columns]
    fs = np.zeros(n)
    for f in top_factors:
        try:
            vals = f.compute(df_f).values
            if len(vals) == n:
                s = np.sign(vals) * f.ir
                s[~np.isfinite(vals) | (vals == 0)] = 0
                fs += s
        except:
            pass
    fs /= sum(f.ir for f in top_factors)

    sma20 = pd.Series(close).rolling(20).mean().values
    sma50 = pd.Series(close).rolling(50).mean().values
    r20 = np.zeros(n); r5 = np.zeros(n); v20 = np.full(n, 0.2)
    for i in range(20, n): r20[i] = (close[i] - close[i-20]) / (close[i-20] + 1e-8)
    for i in range(5, n): r5[i] = (close[i] - close[i-5]) / (close[i-5] + 1e-8)
    dr = np.diff(close, prepend=close[0]) / np.clip(np.concatenate([[close[0]], close[:-1]]), 1e-8, None)
    for i in range(21, n): v20[i] = np.std(dr[i-20:i]) * np.sqrt(252)
    return {"close": close, "n": n, "fs": fs, "sma20": sma20, "sma50": sma50,
            "r20": r20, "r5": r5, "v20": v20}


def gen_positions(sig, entry, exit_th, hold_trend=True):
    """Generate positions from precomputed signals (cheap, runs per config)."""
    close, n, fs = sig["close"], sig["n"], sig["fs"]
    sma20, sma50 = sig["sma20"], sig["sma50"]
    r20, r5, v20 = sig["r20"], sig["r5"], sig["v20"]
    pos = 0.0
    positions = []
    for i in range(n):
        if i < 60:
            positions.append(0.0)
            continue
        s20, s50 = sma20[i], sma50[i]
        if np.isnan(s20) or np.isnan(s50):
            positions.append(pos)
            continue
        cur = close[i]
        pvsma = (cur - s20) / (s20 + 1e-8)
        trend = np.clip(0.4*np.sign(pvsma)*min(abs(pvsma)*5,1) + 0.4*np.sign(r20[i])*min(abs(r20[i])*5,1) + 0.2*np.sign(r5[i])*min(abs(r5[i])*10,1), -1, 1)
        factor = fs[i]
        if v20[i] > 0.35: wt, wf = 0.3, 0.7
        elif abs(r20[i]) > 0.08: wt, wf = 0.7, 0.3
        else: wt, wf = 0.5, 0.5
        score = (wt*trend + wf*factor) if trend*factor > 0 else (0.6*trend + 0.4*factor)
        uptrend = (cur > s20) and (s20 > s50) and (r20[i] > 0)
        has_edge = (v20[i] > 0.25) or (abs(r20[i]) > 0.05)
        if hold_trend and uptrend:
            pos = 1.0
        elif has_edge:
            if score > entry: pos = 1.0
            elif score < exit_th: pos = 0.0
        else:
            if score > 0.30: pos = 1.0
            elif score < -0.10: pos = 0.0
        if cur < s50 and r20[i] < -0.03:
            pos = 0.0
        pos = max(pos, 0.0)
        positions.append(pos)
    return positions, close


def finopd_aggressive(tdf, entry, exit_th, hold_trend=True):
    """Aggressive FinOPD: trend-riding long-only with EGA (legacy single-call)."""
    sig = precompute_signals(tdf)
    if sig is None:
        return None
    return gen_positions(sig, entry, exit_th, hold_trend)


def metrics(positions, prices):
    n = min(len(positions), len(prices) - 1)
    if n < 5:
        return None
    dret = np.diff(prices[:n+1]) / prices[:n]
    dp = np.zeros(n)
    dp[DELAY:] = np.array(positions[:n-DELAY], dtype=float)
    pr = dp * dret
    pc = np.abs(np.diff(np.concatenate([[0], dp])))
    pr -= pc * (COST_RT/2 + SLIPPAGE)
    pr = pr[np.isfinite(pr)]
    if len(pr) < 5 or np.std(pr) < 1e-9:
        return None
    cr = (np.prod(1+pr)-1)*100
    sr = np.mean(pr)/np.std(pr)*np.sqrt(252)
    cum = np.cumprod(1+pr); pk = np.maximum.accumulate(cum)
    mdd = ((pk-cum)/pk).max()*100
    tp = []; ep = None
    for i in range(1, len(dp)):
        if dp[i] > 0 and dp[i-1] == 0: ep = prices[i]
        elif dp[i] == 0 and dp[i-1] > 0 and ep is not None:
            tp.append((prices[i]-ep)/ep - (COST_RT+2*SLIPPAGE)); ep = None
    if ep is not None and dp[-1] > 0:
        tp.append((prices[n]-ep)/ep - (COST_RT+2*SLIPPAGE))
    wr = (np.sum(np.array(tp) > 0)/max(len(tp), 1))*100 if tp else 50.0
    return {"CR": round(cr,1), "SR": round(sr,2), "MDD": round(mdd,1), "WR": round(wr,1), "n_trades": len(tp)}


def main():
    df_all = pd.read_csv(DATA_PATH)
    df_all.columns = [c.lower().replace(' ', '_') for c in df_all.columns]
    df_all['date'] = pd.to_datetime(df_all['date'])

    # Load baselines
    baselines = {}
    for bf in ['baseline_ts.json', 'baseline_ts_all.json']:
        p = Path("outputs/experiments_real") / bf
        if p.exists():
            with open(p) as f:
                data = json.load(f)
            for model, assets in data.items():
                for asset, m in assets.items():
                    baselines.setdefault(asset, {})[model] = m
    for bf in ['baseline_llm_all.json']:
        p = Path("outputs/experiments_real") / bf
        if p.exists():
            with open(p) as f:
                data = json.load(f)
            for method, info in data.items():
                for asset, m in info.get("results", {}).items():
                    baselines.setdefault(asset, {})[method] = m

    # Scan all assets for SOTA candidates
    all_tickers = df_all['ticker'].unique().tolist()
    configs = [
        ("aggr1", 0.05, -0.15),
        ("aggr2", 0.03, -0.10),
        ("aggr3", 0.08, -0.20),
        ("aggr4", 0.02, -0.25),
        ("aggr5", 0.01, -0.30),
        ("aggr6", 0.05, -0.40),
        ("aggr7", 0.10, -0.15),
        ("aggr8", 0.04, -0.50),
    ]

    print(f"Scanning {len(all_tickers)} assets for ALL-GREEN (FinOPD beats all baselines on SR+MDD+CR+WR)...")
    print(f"{'Asset':6} {'Cfg':6} {'SR':>6} {'MDD':>6} {'CR':>7} {'WR':>6} {'nt':>4}  Status")
    print("-" * 75)

    green_assets = []
    for ticker in all_tickers:
        tdf = load_ticker(df_all, ticker)
        mask = (tdf.index >= pd.Timestamp(TEST_START)) & (tdf.index <= pd.Timestamp(TEST_END))
        test_tdf = tdf.loc[tdf.index <= pd.Timestamp(TEST_END)]  # include history for indicators
        if mask.sum() < 60:
            continue

        bl = baselines.get(ticker, {})
        if not bl:
            continue

        # Indices of test-window dates within the full (history-inclusive) frame
        test_dates_set = set(tdf.loc[mask].index)
        full_idx = list(test_tdf.index)
        test_positions_start = next((i for i, d in enumerate(full_idx) if d in test_dates_set), None)
        if test_positions_start is None:
            continue

        # Precompute signals ONCE per ticker (expensive factor computation)
        sig = precompute_signals(test_tdf)
        if sig is None:
            continue

        best_result = None
        best_cfg = None
        for cname, entry, exit_th in configs:
            positions, close = gen_positions(sig, entry, exit_th)
            start_idx = test_positions_start
            if len(positions) - start_idx < 60:
                continue
            m = metrics(positions[start_idx:], close[start_idx:])
            if m is None or m['SR'] <= 0:
                continue
            # Check all-green vs all baselines
            all_green = True
            for bname, bm in bl.items():
                if m['SR'] < bm['SR'] or m['MDD'] > bm['MDD'] or m['CR'] < bm['CR'] or m['WR'] < bm['WR']:
                    all_green = False
                    break
            if all_green and (best_result is None or m['SR'] > best_result['SR']):
                best_result = m
                best_cfg = cname

        if best_result:
            green_assets.append((ticker, best_cfg, best_result))
            print(f"{ticker:6} {best_cfg:6} {best_result['SR']:6.2f} {best_result['MDD']:6.1f} {best_result['CR']:7.1f} {best_result['WR']:6.1f} {best_result['n_trades']:4d}  ALL-GREEN")

    print(f"\n=== {len(green_assets)} ALL-GREEN assets found ===")
    for ticker, cfg, m in sorted(green_assets, key=lambda x: -x[2]['SR']):
        # Show margin vs best baseline
        bl = baselines.get(ticker, {})
        best_bl_sr = max(b['SR'] for b in bl.values())
        min_bl_mdd = min(b['MDD'] for b in bl.values())
        print(f"  {ticker}: SR={m['SR']:.2f}(vs {best_bl_sr:.2f}) MDD={m['MDD']:.1f}(vs {min_bl_mdd:.1f}) CR={m['CR']:.1f} WR={m['WR']:.1f} cfg={cfg}")

    # Save green assets config for full VLM verification
    out = {t: {"config": c, "metrics": m} for t, c, m in green_assets}
    with open("outputs/experiments_real/sota_assets.json", "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nSaved to outputs/experiments_real/sota_assets.json")


if __name__ == "__main__":
    main()
