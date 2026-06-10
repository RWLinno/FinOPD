"""
Build large-scale tri-modal aligned OPD training data.
Each sample: chart IMAGE + time-series TEXT + market CONTEXT text.
"""
from __future__ import annotations
import argparse, json, logging, os, sys
from pathlib import Path
from typing import Dict
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from finvl.visual.renderer import ChartRenderer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("build_opd_multimodal")

SYSTEM_PROMPT = (
    "You are a professional financial multi-modal analyst. "
    "Given a candlestick chart image along with time-series statistics and market context, "
    "predict the short-term (5 trading days) price direction. "
    "Output ONLY valid JSON: "
    '{\"direction\": \"bullish/bearish/neutral\", \"confidence\": 0.0-1.0, '
    '\"action\": \"buy/sell/hold\", \"reasoning\": \"<brief>\", \"expected_return_5d\": <pct>}'
)

def compute_technical_indicators(df):
    close, high, low, volume = df["close"].values, df["high"].values, df["low"].values, df["volume"].values
    n = len(close)
    ind = {}
    if n >= 15:
        d = np.diff(close[-15:])
        ind["rsi_14"] = round(100 - 100/(1 + np.maximum(d,0).mean()/(np.maximum(-d,0).mean()+1e-10)), 1)
    else:
        ind["rsi_14"] = 50.0
    if n >= 26:
        e12 = pd.Series(close).ewm(span=12).mean().iloc[-1]
        e26 = pd.Series(close).ewm(span=26).mean().iloc[-1]
        ind["macd"] = round(float(e12-e26), 4)
        ind["macd_signal"] = "bullish" if e12 > e26 else "bearish"
    else:
        ind["macd"], ind["macd_signal"] = 0.0, "neutral"
    if n >= 15:
        tr = [max(high[-i]-low[-i], abs(high[-i]-close[-i-1]), abs(low[-i]-close[-i-1])) for i in range(1, min(15,n))]
        ind["atr_pct"] = round(float(np.mean(tr))/close[-1]*100, 2)
    else:
        ind["atr_pct"] = 0.0
    ind["volatility_20d"] = round(float(np.std(np.diff(close[-21:])/close[-21:-1])*np.sqrt(252)*100), 1) if n >= 21 else 0.0
    ind["volume_ratio"] = round(float(np.mean(volume[-5:])/(np.mean(volume[-10:-5])+1)), 2) if n >= 10 else 1.0
    if n >= 20:
        ind["price_vs_sma20"] = round((close[-1]/np.mean(close[-20:])-1)*100, 2)
        ind["sma5_vs_sma20"] = round((np.mean(close[-5:])/np.mean(close[-20:])-1)*100, 2)
    else:
        ind["price_vs_sma20"], ind["sma5_vs_sma20"] = 0.0, 0.0
    ind["return_60d"] = round((close[-1]/close[0]-1)*100, 2) if n >= 2 else 0.0
    ind["return_5d"] = round((close[-1]/close[-6]-1)*100, 2) if n >= 6 else 0.0
    return ind

def classify_regime(df):
    if len(df) < 20:
        return "uncertain"
    c = df["close"].values
    rets = np.diff(c[-20:])/c[-20:-1]
    vol = float(np.std(rets)) * np.sqrt(252)
    trend = c[-1]/c[-20]-1
    if vol > 0.4: return "high_volatility"
    elif vol > 0.25:
        return "volatile_uptrend" if trend > 0.05 else ("volatile_downtrend" if trend < -0.05 else "volatile_range")
    elif abs(trend) > 0.08:
        return "strong_trend_up" if trend > 0 else "strong_trend_down"
    elif abs(trend) > 0.03:
        return "moderate_trend_up" if trend > 0 else "moderate_trend_down"
    return "sideways"

def build_timeseries_text(df, ticker, ind):
    c = df["close"].values
    return "\n".join([
        f"[Time-Series Data] {ticker} | Last: ${c[-1]:.2f}",
        f"Window: {len(c)}d ending {df.index[-1].strftime('%Y-%m-%d')}",
        f"Range: ${df['low'].min():.2f}-${df['high'].max():.2f} | Pos: {(c[-1]-df['low'].min())/(df['high'].max()-df['low'].min()+1e-8)*100:.0f}%",
        f"RSI14: {ind['rsi_14']:.1f} | ATR%: {ind['atr_pct']:.2f}% | MACD: {ind['macd_signal']}",
        f"Vol20d: {ind['volatility_20d']:.1f}% | P/SMA20: {ind['price_vs_sma20']:+.2f}%",
        f"Mom5d: {ind['return_5d']:+.2f}% | Trend60d: {ind['return_60d']:+.2f}% | VolR: {ind['volume_ratio']:.2f}",
    ])

def build_context_text(df, ticker, regime, ind):
    r60 = ind["return_60d"]
    td = "strong bullish" if r60>10 else "moderate up" if r60>3 else "range-bound" if r60>-3 else "moderate down" if r60>-10 else "strong bearish"
    v = ind["volatility_20d"]
    vd = "extremely high" if v>40 else "elevated" if v>25 else "normal" if v>15 else "low"
    rsi = ind["rsi_14"]
    rd = "overbought" if rsi>70 else "bullish" if rsi>55 else "neutral" if rsi>45 else "bearish" if rsi>30 else "oversold"
    c = df["close"].values
    sma20 = np.mean(c[-20:]) if len(c)>=20 else c[-1]
    return "\n".join([
        f"[Market Context] Regime: {regime.replace('_',' ')}",
        f"Trend: {td} | Volatility: {vd} | RSI: {rd}",
        f"SMA20: ${sma20:.2f} ({'support' if c[-1]>sma20 else 'resistance'})",
    ])

def compute_label(df_future, threshold=0.5):
    if df_future is None or len(df_future) < 3:
        return None
    fwd = (df_future["close"].iloc[min(4,len(df_future)-1)]/df_future["close"].iloc[0]-1)*100
    if fwd > threshold: d, a = "bullish", "buy"
    elif fwd < -threshold: d, a = "bearish", "sell"
    else: d, a = "neutral", "hold"
    conf = min(abs(fwd)/5.0, 1.0) if d != "neutral" else 0.3
    return d, conf, a, round(fwd, 2)

def build_dataset(data_path, output_dir, lookback=60, sample_every=5, max_samples=12000,
                  start_date="2018-06-01", end_date="2024-12-31", direction_threshold=0.5):
    output = Path(output_dir)
    charts_dir = output / "charts"
    charts_dir.mkdir(parents=True, exist_ok=True)
    df_all = pd.read_csv(data_path, parse_dates=["date"])
    tickers = sorted(df_all["ticker"].unique())
    logger.info(f"Loaded {len(df_all)} rows, {len(tickers)} tickers")
    renderer = ChartRenderer({"output_dir": str(charts_dir), "dpi": 100, "image_size": [800, 600]})
    samples, stats = [], {"bullish": 0, "bearish": 0, "neutral": 0}

    for ticker in tickers:
        dt = df_all[df_all["ticker"]==ticker].copy().sort_values("date").reset_index(drop=True)
        dt.set_index("date", inplace=True)
        dt = dt[(dt.index >= start_date) & (dt.index <= end_date)]
        if len(dt) < lookback+10:
            continue
        dates = dt.index[lookback::sample_every]
        logger.info(f"  {ticker}: {len(dates)} candidates")
        for date in dates:
            if len(samples) >= max_samples:
                break
            loc = dt.index.get_loc(date)
            if loc < lookback:
                continue
            window = dt.iloc[loc-lookback:loc+1]
            fe = min(loc+6, len(dt))
            if fe <= loc+1:
                continue
            result = compute_label(dt.iloc[loc:fe], direction_threshold)
            if result is None:
                continue
            direction, confidence, action, fwd_ret = result
            ds = date.strftime("%Y-%m-%d")
            cp = str(charts_dir / f"{ticker}_{ds}.png")
            if not os.path.exists(cp):
                try:
                    rdf = window.drop(columns=[c for c in window.columns if c in ("adj close","adj_close","ticker")], errors="ignore")
                    if not all(c in rdf.columns for c in ["open","high","low","close","volume"]):
                        continue
                    renderer.render_candlestick(rdf, asset=ticker, overlays=[{"type":"sma","periods":[5,20]},{"type":"bollinger","period":20,"std":2}], save_path=cp)
                except:
                    continue
            if not os.path.exists(cp):
                continue
            ind = compute_technical_indicators(window)
            regime = classify_regime(window)
            user_content = f"<image>\n{build_timeseries_text(window,ticker,ind)}\n\n{build_context_text(window,ticker,regime,ind)}\n\nPredict the 5-day direction for {ticker}."
            asst = json.dumps({"direction":direction,"confidence":round(confidence,3),"action":action,"reasoning":f"{regime.replace('_',' ')} with {ind['return_5d']:+.1f}% momentum","expected_return_5d":fwd_ret})
            samples.append({"messages":[{"role":"system","content":SYSTEM_PROMPT},{"role":"user","content":user_content},{"role":"assistant","content":asst}],
                "images":[str(Path(cp).relative_to(Path(output_dir).parent.parent))],"ticker":ticker,"date":ds,"fwd_return":fwd_ret/100.0,"regime":regime})
            stats[direction] += 1
        if len(samples) >= max_samples:
            break

    with open(output/"opd_multimodal.jsonl","w") as f:
        for s in samples:
            f.write(json.dumps(s,ensure_ascii=False)+"\n")
    logger.info(f"=== Built {len(samples)} samples, dist={stats}, tickers={len(set(s['ticker'] for s in samples))} ===")
    json.dump({"total":len(samples),"dist":stats,"tickers":sorted(set(s["ticker"] for s in samples))},
              open(output/"dataset_meta.json","w"), indent=2)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data", default="data/processed/us_dow30.csv")
    p.add_argument("--output-dir", default="data/opd_train_v2")
    p.add_argument("--lookback", type=int, default=60)
    p.add_argument("--sample-every", type=int, default=5)
    p.add_argument("--max-samples", type=int, default=12000)
    p.add_argument("--start-date", default="2018-06-01")
    p.add_argument("--end-date", default="2024-12-31")
    p.add_argument("--threshold", type=float, default=0.5)
    a = p.parse_args()
    build_dataset(a.data, a.output_dir, a.lookback, a.sample_every, a.max_samples, a.start_date, a.end_date, a.threshold)

if __name__ == "__main__":
    main()
