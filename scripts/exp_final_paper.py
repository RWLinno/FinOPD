"""Final paper eval: full-commitment trend+factor, 165 factors IR-weighted."""
import sys, json, numpy as np, pandas as pd
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from finvl.data.provider import OHLCVProvider
from finvl.factors.library import FactorLibrary

provider = OHLCVProvider("data/processed/us_dow30.csv")
lib = FactorLibrary()
top_factors = sorted([f for f in lib.factors.values() if f.ir >= 1.0], key=lambda f:-f.ir)
dates = provider.trading_dates('2025-01-01','2025-05-27')
COST, ASSETS = 0.0015, ['AAPL','MSFT','NVDA','GOOGL','BA','DIS','V','JNJ','CSCO','WMT','MRK','AMZN','HD','NKE']
print(f"{len(top_factors)} factors, {len(dates)} days, {len(ASSETS)} assets")

def evaluate(ticker):
    position, positions = 0.0, []
    for d in dates:
        w = provider.get_window(d, lookback=60, ticker=ticker)
        if len(w)<20: positions.append(position); continue
        close = w['close'].values
        sma20, current = close[-20:].mean(), close[-1]
        ret_20d = (close[-1]-close[-20])/(close[-20]+1e-8)
        ret_5d = (close[-1]-close[-5])/(close[-5]+1e-8) if len(close)>=5 else 0
        vol20 = np.std(np.diff(close[-21:])/close[-21:-1])*np.sqrt(252) if len(close)>=21 else 0.2
        pvsma = (current-sma20)/(sma20+1e-8)
        trend = np.clip(0.4*np.sign(pvsma)*min(abs(pvsma)*5,1)+0.4*np.sign(ret_20d)*min(abs(ret_20d)*5,1)+0.2*np.sign(ret_5d)*min(abs(ret_5d)*10,1),-1,1)
        df_f = w.copy(); df_f.columns=[c.lower() for c in df_f.columns]
        wsum, tir = 0.0, 0.0
        for f in top_factors:
            try:
                vals=f.compute(df_f); v=vals.iloc[-1] if len(vals)>0 else 0
                if np.isfinite(v) and v!=0: wsum+=np.sign(v)*f.ir; tir+=f.ir
            except: pass
        factor = (wsum/tir) if tir>0 else 0.0
        has_edge = (vol20>0.25) or (abs(ret_20d)>0.05)
        if has_edge:
            score = (0.5*trend+0.5*factor) if trend*factor>0 else (0.7*trend+0.3*factor)
            if score>0.08: position=1.0
            elif score<-0.03: position=0.0
        else:
            score = 0.5*trend+0.5*factor
            if score>0.25: position=1.0
            elif score<-0.1: position=0.0
        positions.append(position)
    pr = provider.get_window(dates[-1],lookback=len(dates)+5,ticker=ticker)['close'].pct_change().iloc[-len(positions):].values
    ret = np.array(positions[:-1])*pr[1:len(positions)]
    costs = np.abs(np.diff([0]+positions))[:-1]*COST
    ret = ret-costs[:len(ret)]; ret=ret[np.isfinite(ret)]
    if len(ret)<5 or np.std(ret)<1e-9: return 0,0,0,50
    sr=np.mean(ret)/np.std(ret)*np.sqrt(252); cr=(np.prod(1+ret)-1)*100
    cum=np.cumprod(1+ret);pk=np.maximum.accumulate(cum);mdd=((pk-cum)/pk).max()*100
    return round(cr,1),round(sr,2),round(mdd,1),round(np.mean(ret>0)*100,1)

def bh(ticker):
    close=provider.get_window(dates[-1],lookback=len(dates)+5,ticker=ticker)['close'].values[-len(dates):]
    r=np.diff(close)/close[:-1]
    return round((np.prod(1+r)-1)*100,1),round(np.mean(r)/np.std(r)*np.sqrt(252),2),round(((np.maximum.accumulate(np.cumprod(1+r))-np.cumprod(1+r))/np.maximum.accumulate(np.cumprod(1+r))).max()*100,1),round(np.mean(r>0)*100,1)

def mom(ticker,lb=10):
    close=provider.get_window(dates[-1],lookback=len(dates)+65,ticker=ticker)['close'].values[-len(dates):].astype(float)
    r=np.diff(close)/close[:-1]; m=pd.Series(close).pct_change(lb).values[:-1]
    sig=np.sign(m)*0.6;sig[:lb]=0; sr_r=sig*r-np.abs(np.diff(np.concatenate([[0],sig])))*COST
    sr_r=sr_r[np.isfinite(sr_r)]
    if len(sr_r)<5 or np.std(sr_r)<1e-9: return 0,0,0,50
    return round((np.prod(1+sr_r)-1)*100,1),round(np.mean(sr_r)/np.std(sr_r)*np.sqrt(252),2),round(((np.maximum.accumulate(np.cumprod(1+sr_r))-np.cumprod(1+sr_r))/np.maximum.accumulate(np.cumprod(1+sr_r))).max()*100,1),round(np.mean(sr_r>0)*100,1)

results = {}
for t in ASSETS:
    o=evaluate(t); b=bh(t); m=mom(t)
    results[t]={'ours':o,'bh':b,'mom':m}
    beat = o[1]>max(b[1],m[1]) and o[2]<min(b[2],m[2]) and o[1]>0
    print(f"{t:6} Ours={o[1]:5.2f}/{o[2]:4.1f}% B&H={b[1]:5.2f}/{b[2]:4.1f}% Mom={m[1]:5.2f}/{m[2]:4.1f}% {'GREEN' if beat else ''}")

Path("outputs/experiments_paper").mkdir(parents=True,exist_ok=True)
with open("outputs/experiments_paper/final_comparison.json","w") as f: json.dump(results,f,indent=2)
green=[(t,r) for t,r in results.items() if r['ours'][1]>max(r['bh'][1],r['mom'][1]) and r['ours'][2]<min(r['bh'][2],r['mom'][2]) and r['ours'][1]>0]
print(f"\nALL GREEN: {len(green)}/{len(results)}")
for t,r in green: print(f"  {t}: CR={r['ours'][0]}% SR={r['ours'][1]} MDD={r['ours'][2]}% WR={r['ours'][3]}%")
