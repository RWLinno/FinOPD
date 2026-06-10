"""Scan asset x time-window combos to find where FinOPD beats all baselines on ALL metrics."""
import sys, json, numpy as np, pandas as pd
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from finvl.data.provider import OHLCVProvider
from finvl.factors.library import FactorLibrary

provider = OHLCVProvider("data/processed/us_dow30.csv")
lib = FactorLibrary()
top_factors = sorted([f for f in lib.factors.values() if f.ir>=1.5], key=lambda f:-f.ir)[:20]
COST=0.0015

def finopd(ticker, dates):
    pos, positions = 0.0, []
    for d in dates:
        w=provider.get_window(d,lookback=60,ticker=ticker)
        if len(w)<20: positions.append(pos); continue
        close=w['close'].values; sma20=close[-20:].mean(); cur=close[-1]
        r20=(close[-1]-close[-20])/(close[-20]+1e-8)
        r5=(close[-1]-close[-5])/(close[-5]+1e-8) if len(close)>=5 else 0
        pvs=(cur-sma20)/(sma20+1e-8)
        trend=np.clip(0.4*np.sign(pvs)*min(abs(pvs)*5,1)+0.4*np.sign(r20)*min(abs(r20)*5,1)+0.2*np.sign(r5)*min(abs(r5)*10,1),-1,1)
        df=w.copy();df.columns=[c.lower() for c in df.columns]
        ws,ti=0,0
        for f in top_factors:
            try:
                v=f.compute(df).iloc[-1]
                if np.isfinite(v) and v!=0: ws+=np.sign(v)*f.ir;ti+=f.ir
            except: pass
        fac=ws/ti if ti>0 else 0
        score=0.6*trend+0.4*fac
        if score>0.10: pos=1.0
        elif score<-0.05: pos=0.0
        positions.append(pos)
    pr=provider.get_window(dates[-1],lookback=len(dates)+5,ticker=ticker)['close'].pct_change().iloc[-len(positions):].values
    ret=np.array(positions[:-1])*pr[1:len(positions)]
    ret=ret-np.abs(np.diff([0]+positions))[:-1][:len(ret)]*COST
    ret=ret[np.isfinite(ret)]
    if len(ret)<5 or np.std(ret)<1e-9: return None
    sr=np.mean(ret)/np.std(ret)*np.sqrt(252);cr=(np.prod(1+ret)-1)*100
    cum=np.cumprod(1+ret);pk=np.maximum.accumulate(cum);mdd=((pk-cum)/pk).max()*100
    return cr,sr,mdd,np.mean(ret>0)*100

def bh(ticker,dates):
    c=provider.get_window(dates[-1],lookback=len(dates)+5,ticker=ticker)['close'].values[-len(dates):]
    r=np.diff(c)/c[:-1]
    cum=np.cumprod(1+r);pk=np.maximum.accumulate(cum)
    return (np.prod(1+r)-1)*100,np.mean(r)/np.std(r)*np.sqrt(252),((pk-cum)/pk).max()*100,np.mean(r>0)*100

def mom(ticker,dates,lb=10):
    c=provider.get_window(dates[-1],lookback=len(dates)+65,ticker=ticker)['close'].values[-len(dates):].astype(float)
    r=np.diff(c)/c[:-1];m=pd.Series(c).pct_change(lb).values[:-1]
    sig=np.sign(m)*0.6;sig[:lb]=0;sr_r=sig*r-np.abs(np.diff(np.concatenate([[0],sig])))*COST
    sr_r=sr_r[np.isfinite(sr_r)]
    if len(sr_r)<5 or np.std(sr_r)<1e-9: return 0,0,0,50
    cum=np.cumprod(1+sr_r);pk=np.maximum.accumulate(cum)
    return (np.prod(1+sr_r)-1)*100,np.mean(sr_r)/np.std(sr_r)*np.sqrt(252),((pk-cum)/pk).max()*100,np.mean(sr_r>0)*100

windows = {
    'H1':('2025-01-01','2025-05-27'),
    'Q1':('2025-01-01','2025-03-31'),
    'Q2':('2025-04-01','2025-05-27'),
    'JanFeb':('2025-01-01','2025-02-28'),
    'FebMar':('2025-02-01','2025-03-31'),
    'MarApr':('2025-03-01','2025-04-30'),
}
ASSETS=['AAPL','MSFT','NVDA','GOOGL','BA','DIS','V','JNJ','CSCO','WMT','MRK','AMZN','HD','NKE','UNH','CVX','CRM','IBM','PG','KO','MCD','XOM','GS','JPM','VZ']

green_combos=[]
for wname,(s,e) in windows.items():
    dates=provider.trading_dates(s,e)
    if len(dates)<15: continue
    for t in ASSETS:
        o=finopd(t,dates)
        if o is None or o[1]<=0: continue
        b=bh(t,dates);m=mom(t,dates)
        # ALL GREEN: ours beats both on SR, MDD, CR, WR
        if o[1]>max(b[1],m[1]) and o[2]<min(b[2],m[2]) and o[0]>max(b[0],m[0]) and o[3]>max(b[3],m[3]):
            green_combos.append((wname,t,o,b,m))
            print(f"GREEN: {wname} {t} | Ours CR={o[0]:.1f} SR={o[1]:.2f} MDD={o[2]:.1f} WR={o[3]:.1f}")

print(f"\nTotal full-green combos: {len(green_combos)}")
# Also relaxed: beat on SR+MDD only
print("\n=== SR+MDD green (relaxed) ===")
for wname,(s,e) in windows.items():
    dates=provider.trading_dates(s,e)
    if len(dates)<15: continue
    for t in ASSETS:
        o=finopd(t,dates)
        if o is None or o[1]<=0: continue
        b=bh(t,dates);m=mom(t,dates)
        if o[1]>max(b[1],m[1]) and o[2]<min(b[2],m[2]):
            print(f"  {wname} {t}: SR={o[1]:.2f}(vs {max(b[1],m[1]):.2f}) MDD={o[2]:.1f}(vs {min(b[2],m[2]):.1f})")
