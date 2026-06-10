"""Quick scan: find per-asset best config with WR>=80%."""
import sys, numpy as np, pandas as pd, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, 'src')
from finvl.factors.library import FactorLibrary

df = pd.read_csv('data/processed/us_dow30.csv')
df.columns = [c.lower().replace(' ', '_') for c in df.columns]
df['date'] = pd.to_datetime(df['date'])
df = df.sort_values(['ticker', 'date'])
lib = FactorLibrary()
top_factors = sorted([f for f in lib.factors.values() if f.ir >= 1.0], key=lambda f: -f.ir)
COST_RT, SLIPPAGE, DELAY = 0.0015, 0.0005, 1

def run(tdf, entry, exit_th, ne_entry, ne_exit):
    close = tdf['close'].values.astype(float); n = len(close)
    if n < 60: return None
    df_f = tdf.copy(); df_f.columns = [c.lower() for c in df_f.columns]
    fs = np.zeros(n)
    for f in top_factors:
        try:
            vals = f.compute(df_f).values
            if len(vals)==n:
                s=np.sign(vals)*f.ir; s[~np.isfinite(vals)|(vals==0)]=0; fs+=s
        except: pass
    fs /= sum(f.ir for f in top_factors)
    sma20 = pd.Series(close).rolling(20).mean().values
    r20=np.zeros(n); r5=np.zeros(n); v20=np.full(n,0.2)
    for i in range(20,n): r20[i]=(close[i]-close[i-20])/(close[i-20]+1e-8)
    for i in range(5,n): r5[i]=(close[i]-close[i-5])/(close[i-5]+1e-8)
    dr=np.diff(close,prepend=close[0])/np.clip(np.concatenate([[close[0]],close[:-1]]),1e-8,None)
    for i in range(21,n): v20[i]=np.std(dr[i-20:i])*np.sqrt(252)
    pos=0.0; positions=[]
    for i in range(n):
        if i<60: positions.append(0.0); continue
        s20=sma20[i]
        if np.isnan(s20): positions.append(pos); continue
        cur=close[i]; pv=(cur-s20)/(s20+1e-8)
        trend=np.clip(0.4*np.sign(pv)*min(abs(pv)*5,1)+0.4*np.sign(r20[i])*min(abs(r20[i])*5,1)+0.2*np.sign(r5[i])*min(abs(r5[i])*10,1),-1,1)
        factor=fs[i]; vv=v20[i]
        wt,wf=(0.3,0.7) if vv>0.35 else ((0.7,0.3) if abs(r20[i])>0.08 else (0.5,0.5))
        score=(wt*trend+wf*factor) if trend*factor>0 else (0.6*trend+0.4*factor)
        he=(vv>0.25)or(abs(r20[i])>0.05)
        if he:
            if score>entry: pos=1.0
            elif score<exit_th: pos=0.0
        else:
            if score>ne_entry: pos=1.0
            elif score<ne_exit: pos=0.0
        pos=max(pos,0.0); positions.append(pos)
    prices=close; nn=min(len(positions),len(prices)-1)
    dret=np.diff(prices[:nn+1])/prices[:nn]
    dp=np.zeros(nn); dp[DELAY:]=np.array(positions[:nn-DELAY],dtype=float)
    pr=dp*dret; pc=np.abs(np.diff(np.concatenate([[0],dp]))); pr-=pc*(COST_RT/2+SLIPPAGE)
    pr=pr[np.isfinite(pr)]
    if len(pr)<5 or np.std(pr)<1e-9: return None
    cr=(np.prod(1+pr)-1)*100; sr=np.mean(pr)/np.std(pr)*np.sqrt(252)
    cum=np.cumprod(1+pr); pk=np.maximum.accumulate(cum); mdd=((pk-cum)/pk).max()*100
    tp=[]; ep=None
    for i in range(1,len(dp)):
        if dp[i]>0 and dp[i-1]==0: ep=prices[i]
        elif dp[i]==0 and dp[i-1]>0 and ep is not None: tp.append((prices[i]-ep)/ep-(COST_RT+2*SLIPPAGE)); ep=None
    if ep is not None and dp[-1]>0: tp.append((prices[nn]-ep)/ep-(COST_RT+2*SLIPPAGE))
    wr=(np.sum(np.array(tp)>0)/max(len(tp),1))*100 if tp else 50.0
    return cr, sr, mdd, wr, len(tp)

targets = ['GOOGL','JNJ','AAPL','GS','MSFT','UNH','NVDA','CSCO','IBM','MCD','DIS','BA']
start, end = '2025-04-01', '2025-12-31'
params = [
    (0.08,-0.15,0.20,-0.08),
    (0.10,-0.20,0.25,-0.10),
    (0.12,-0.25,0.30,-0.15),
    (0.15,-0.30,0.35,-0.20),
    (0.20,-0.30,0.40,-0.25),
]
print(f'Asset   CR     SR    MDD    WR  nt cfg')
for t in targets:
    sub = df[df['ticker']==t].set_index('date').sort_index()
    mask = (sub.index >= pd.Timestamp(start)) & (sub.index <= pd.Timestamp(end))
    tdf = sub.loc[mask]
    if len(tdf) < 60: continue
    best = None; bc = -1
    for ci, (e,x,ne,nx) in enumerate(params):
        r = run(tdf, e, x, ne, nx)
        if r and r[1] > 0:
            # Prefer WR >= 80, then highest SR
            if best is None or (r[3] >= 80 and best[3] < 80) or (r[3] >= 80 and best[3] >= 80 and r[1] > best[1]) or (r[3] < 80 and best[3] < 80 and r[1] > best[1]):
                best = r; bc = ci
    if best:
        flag = '*' if best[3] >= 80 else ' '
        print(f'{t:7} {best[0]:6.1f} {best[1]:5.2f} {best[2]:5.1f} {best[3]:5.1f} {best[4]:3d} p{bc} {flag}')
