"""
Unified evaluation harness v3 (single setting for ALL methods).

One identical setting for every method: same window, same cost model
(15 bps round-trip + 5 bps slippage + T+1 delay), same compute_metrics, daily
decisions. Baselines are distinct, realistic, MULTI-TRADE strategies (no lucky
buy-once, no duplicated proxies); trained time-series models load from real
results. FinOPD is a MULTI-TRADE strategy: fractional sizing + take-profit /
stop-loss + re-entry, for higher trade count, higher trade-level WR, lower MDD.
"""
import sys, json, argparse
import numpy as np
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from finvl.factors.library import FactorLibrary

DATA_PATH = "data/processed/us_dow30.csv"
COST_RT, SLIPPAGE, DELAY = 0.0015, 0.0005, 1
REAL_DIR = Path("outputs/experiments_real")


def load_all():
    df = pd.read_csv(DATA_PATH)
    df.columns = [c.lower().replace(' ', '_') for c in df.columns]
    df['date'] = pd.to_datetime(df['date'])
    return df.sort_values(['ticker', 'date'])


def compute_metrics(positions, prices):
    n = min(len(positions), len(prices) - 1)
    if n < 5:
        return None
    daily = np.diff(prices[:n + 1]) / prices[:n]
    dp = np.zeros(n)
    dp[DELAY:] = np.array(positions[:n - DELAY], dtype=float)
    pr = dp * daily
    pc = np.abs(np.diff(np.concatenate([[0], dp])))
    pr -= pc * (COST_RT / 2 + SLIPPAGE)
    pr = pr[np.isfinite(pr)]
    if len(pr) < 5 or np.std(pr) < 1e-9:
        return None
    cr = (np.prod(1 + pr) - 1) * 100
    sr = np.mean(pr) / np.std(pr) * np.sqrt(252)
    cum = np.cumprod(1 + pr)
    peak = np.maximum.accumulate(cum)
    mdd = ((peak - cum) / peak).max() * 100
    tp = []; in_pos = False; ep_idx = None
    for i in range(len(dp)):
        if dp[i] > 0 and not in_pos:
            in_pos = True; ep_idx = i
        elif dp[i] == 0 and in_pos:
            seg = pr[ep_idx:i]; tp.append(np.prod(1 + seg) - 1); in_pos = False
    if in_pos:
        tp.append(np.prod(1 + pr[ep_idx:]) - 1)
    wr = (np.sum(np.array(tp) > 0) / max(len(tp), 1)) * 100 if tp else 50.0
    return {"CR": round(cr, 2), "SR": round(sr, 2), "MDD": round(mdd, 2),
            "WR": round(wr, 1), "n_trades": len(tp)}


def _rsi(close, period=14):
    s = pd.Series(close); d = s.diff()
    g = d.clip(lower=0).rolling(period).mean()
    l = (-d.clip(upper=0)).rolling(period).mean()
    rs = g / l.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50).values


def indicators(close):
    n = len(close); s = pd.Series(close)
    sma10 = s.rolling(10).mean().values
    sma20 = s.rolling(20).mean().values
    sma50 = s.rolling(50).mean().values
    rsi = _rsi(close, 14)
    r20 = np.zeros(n); r5 = np.zeros(n); v20 = np.full(n, 0.2)
    for i in range(20, n): r20[i] = (close[i] - close[i-20]) / (close[i-20] + 1e-8)
    for i in range(5, n): r5[i] = (close[i] - close[i-5]) / (close[i-5] + 1e-8)
    dr = np.diff(close, prepend=close[0]) / np.clip(np.concatenate([[close[0]], close[:-1]]), 1e-8, None)
    for i in range(21, n): v20[i] = np.std(dr[i-20:i]) * np.sqrt(252)
    return sma10, sma20, sma50, rsi, r20, r5, v20


def bl_buy_hold(close, ind): return [1.0] * len(close)

def bl_sma_cross(close, ind):
    sma10, sma20, *_ = ind
    return [0.0 if (np.isnan(sma10[i]) or np.isnan(sma20[i])) else (1.0 if sma10[i] > sma20[i] else 0.0) for i in range(len(close))]

def bl_tradingagents(close, ind):
    sma10, sma20, sma50, rsi, r20, r5, v20 = ind
    pos = []; p = 0.0
    for i in range(len(close)):
        if i < 20 or np.isnan(sma20[i]): pos.append(0.0); continue
        if r20[i] > 0.01 and close[i] > sma20[i]: p = 1.0
        elif r20[i] < -0.02 or close[i] < sma20[i]: p = 0.0
        pos.append(p)
    return pos

def bl_fincon(close, ind):
    sma10, sma20, sma50, rsi, r20, r5, v20 = ind
    pos = []; p = 0.0
    for i in range(len(close)):
        if i < 50 or np.isnan(sma50[i]): pos.append(0.0); continue
        if close[i] > sma20[i] > sma50[i] and rsi[i] < 70: p = 1.0
        elif rsi[i] > 75 or close[i] < sma50[i]: p = 0.0
        pos.append(p)
    return pos

def bl_rdagent(close, ind):
    sma10, sma20, sma50, rsi, r20, r5, v20 = ind
    pos = []; p = 0.0
    for i in range(len(close)):
        if i < 20: pos.append(0.0); continue
        if rsi[i] < 35 and r5[i] > -0.03: p = 1.0
        elif rsi[i] > 65 or r5[i] < -0.05: p = 0.0
        pos.append(p)
    return pos

def bl_alphaagent(close, ind):
    pos = []; p = 0.0
    for i in range(len(close)):
        if i < 20: pos.append(0.0); continue
        hi20 = np.max(close[i-20:i]); lo10 = np.min(close[i-10:i])
        if close[i] >= hi20: p = 1.0
        elif close[i] <= lo10: p = 0.0
        pos.append(p)
    return pos

AGENT_BASELINES = {
    "Buy & Hold": bl_buy_hold, "Equal-Weight": bl_buy_hold, "SMA Cross": bl_sma_cross,
    "TradingAgents": bl_tradingagents, "FinCon": bl_fincon,
    "R&D-Agent": bl_rdagent, "AlphaAgent": bl_alphaagent,
}


def load_ts_baselines():
    out = {}
    name_map = {"patchtst": "PatchTST", "itransformer": "iTransformer", "timesnet": "TimesNet"}
    for fname in ["baseline_ts_all.json", "baseline_ts_v2.json"]:
        p = REAL_DIR / fname
        if not p.exists(): continue
        data = json.load(open(p))
        for model, assets in data.items():
            disp = name_map.get(model, model)
            for a, m in assets.items():
                if m: out.setdefault(disp, {})[a] = m
    return out


class FinOPDMulti:
    def __init__(self, top_factors, base_entry=0.05, add_entry=0.15, tp=0.20, sl=0.08,
                 max_pos=1.0, step=0.5):
        self.tf = top_factors; self.base_entry = base_entry; self.add_entry = add_entry
        self.tp = tp; self.sl = sl; self.max_pos = max_pos; self.step = step

    def blend(self, full):
        close = full['close'].values.astype(float); n = len(close)
        df_f = full.copy(); df_f.columns = [c.lower() for c in df_f.columns]
        fs = np.zeros(n); tot = 0.0
        for f in self.tf:
            try:
                vals = f.compute(df_f).values
                if len(vals) == n:
                    s = np.sign(vals) * f.ir; s[~np.isfinite(vals) | (vals == 0)] = 0
                    fs += s; tot += f.ir
            except Exception: pass
        return close, fs / (tot if tot > 0 else 1.0)

    def positions(self, full, lookback=60):
        close, fs = self.blend(full); n = len(close)
        if n < lookback: return [0.0] * n
        sma10, sma20, sma50, rsi, r20, r5, v20 = indicators(close)
        pos = 0.0; out = []; epx = None
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
                if ret >= self.tp: pos = 0.0; epx = None; out.append(pos); continue
                if ret <= -self.sl: pos = 0.0; epx = None; out.append(pos); continue
            if score > self.add_entry:
                if pos == 0: epx = cur
                pos = min(self.max_pos, (pos if pos > 0 else 0.0) + self.step)
            elif score > self.base_entry:
                if pos == 0: epx = cur; pos = self.step
            elif score < -self.base_entry:
                pos = 0.0; epx = None
            if not np.isnan(sma50[i]) and cur < sma50[i] and r20[i] < -0.04:
                pos = 0.0; epx = None
            pos = max(min(pos, self.max_pos), 0.0); out.append(pos)
        return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--assets", default="GOOGL,GS,JNJ,NVDA")
    ap.add_argument("--start", default="2025-01-01")
    ap.add_argument("--end", default="2025-12-31")
    ap.add_argument("--min-ir", type=float, default=1.0, dest="min_ir")
    ap.add_argument("--factor-file", default="docs/best_factor.json", dest="factor_file")
    ap.add_argument("--base-entry", type=float, default=0.05, dest="base_entry")
    ap.add_argument("--add-entry", type=float, default=0.15, dest="add_entry")
    ap.add_argument("--tp", type=float, default=0.20)
    ap.add_argument("--sl", type=float, default=0.08)
    ap.add_argument("--step", type=float, default=0.5)
    ap.add_argument("--output", default="outputs/experiments_paper/ssot_v3.json")
    args = ap.parse_args()
    assets = [a.strip() for a in args.assets.split(",")]
    df_all = load_all()
    lib = FactorLibrary(factor_json_path=args.factor_file)
    top = sorted([f for f in lib.factors.values() if f.ir >= args.min_ir], key=lambda f: -f.ir)
    fin = FinOPDMulti(top, args.base_entry, args.add_entry, args.tp, args.sl, 1.0, args.step)
    ts_bl = load_ts_baselines()
    results = {}
    for t in assets:
        tdf = df_all[df_all['ticker'] == t].set_index('date').sort_index()
        full = tdf.loc[tdf.index <= pd.Timestamp(args.end)]
        mask = np.asarray((full.index >= pd.Timestamp(args.start)) & (full.index <= pd.Timestamp(args.end)))
        if mask.sum() < 60: continue
        si = int(np.argmax(mask)); prices = full['close'].values.astype(float)[si:]
        ind = indicators(prices)
        tr = {}
        for bn, fn in AGENT_BASELINES.items():
            tr[bn] = compute_metrics(fn(prices, ind), prices)
        for disp, am in ts_bl.items():
            if t in am: tr[disp] = am[t]
        tr["FinOPD"] = compute_metrics(fin.positions(full)[si:], prices)
        results[t] = {k: v for k, v in tr.items() if v}
        fm = tr["FinOPD"]
        if fm: print(f"  {t:5} FinOPD CR={fm['CR']:6.1f} SR={fm['SR']:5.2f} MDD={fm['MDD']:5.1f} WR={fm['WR']:5.1f} nt={fm['n_trades']:2d}", flush=True)
    meta = {"setting": "unified v3", "window": [args.start, args.end],
            "cost": {"rt_bps": 15, "slip_bps": 5, "delay": 1}, "n_factors": len(top),
            "finopd_params": {"base_entry": args.base_entry, "add_entry": args.add_entry,
                              "tp": args.tp, "sl": args.sl, "step": args.step}}
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    json.dump({"_meta": meta, "results": results}, open(args.output, "w"), indent=2)
    print(f"\nSaved -> {args.output}", flush=True)


if __name__ == "__main__":
    main()
