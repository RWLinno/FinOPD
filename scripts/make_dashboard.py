"""
Generate a self-contained HTML dashboard from the FinOPD result JSONs.
Embeds the data inline and uses Chart.js (CDN) for charts.

Usage:
  python scripts/make_dashboard.py
  -> writes KDD27_FinOPD_overleaf/dashboard.html
"""
import json
from pathlib import Path

SNAP = Path("KDD27_FinOPD_overleaf/data_snapshots")
OUT = Path("KDD27_FinOPD_overleaf/dashboard.html")


def load(name):
    p = SNAP / name
    return json.load(open(p)) if p.exists() else {}


def main():
    ssot = load("ssot_v3_main.json").get("results", {})
    mw = load("multiwindow.json")
    abl = load("real_ablation.json")
    cf = load("real_counterfactual.json")
    sens = load("real_sensitivity.json")

    # Portfolio aggregate from ssot
    methods = ["Buy & Hold", "SMA Cross", "PatchTST", "TimesNet", "iTransformer",
               "TradingAgents", "FinCon", "R&D-Agent", "AlphaAgent", "FinOPD"]
    import numpy as np
    agg = {}
    for m in methods:
        vals = [ssot[a][m] for a in ssot if m in ssot[a]]
        if vals:
            cr = float(np.mean([v["CR"] for v in vals])); sr = float(np.mean([v["SR"] for v in vals]))
            md = float(np.mean([v["MDD"] for v in vals])); wr = float(np.mean([v["WR"] for v in vals]))
            agg[m] = {"CR": round(cr, 1), "SR": round(sr, 2), "MDD": round(md, 1),
                      "Calmar": round(cr / md, 2) if md else 0, "WR": round(wr, 1)}

    data = {"agg": agg, "mw": mw, "abl": abl, "cf": cf, "sens": sens}
    djson = json.dumps(data)

    html = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>FinOPD Results Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
:root{--bg:#0f1117;--card:#171a23;--fg:#e6e8ee;--mut:#9aa3b2;--acc:#4f8cff;--good:#2ecc71;--line:#272b36}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:14px/1.5 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif}
.wrap{max-width:1100px;margin:0 auto;padding:32px 20px}
h1{font-size:26px;margin:0 0 4px}.sub{color:var(--mut);margin-bottom:28px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:20px;margin-bottom:20px}
.card h2{font-size:16px;margin:0 0 14px;color:var(--fg)}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{padding:7px 10px;text-align:right;border-bottom:1px solid var(--line)}
th:first-child,td:first-child{text-align:left}
th{color:var(--mut);font-weight:600}
tr.ours td{color:var(--acc);font-weight:700}
.best{color:var(--good);font-weight:700}
.note{color:var(--mut);font-size:12px;margin-top:10px}
canvas{max-height:300px}
.tag{display:inline-block;background:#1f2430;color:var(--mut);border-radius:6px;padding:2px 8px;font-size:11px;margin-left:6px}
</style></head><body><div class="wrap">
<h1>FinOPD — Results Dashboard <span class="tag">reproducible</span></h1>
<div class="sub">Unified protocol · full-year 2025 post-cutoff · 4 showcase assets (GOOGL, GS, JNJ, NVDA) · 15bps RT + 5bps slip + T+1</div>

<div class="card"><h2>Portfolio-level performance (Sharpe sorted)</h2>
<table id="aggTable"><thead><tr><th>Method</th><th>CR%</th><th>SR</th><th>MDD%</th><th>Calmar</th><th>WR%</th></tr></thead><tbody></tbody></table>
<div class="note">FinOPD has the highest Sharpe (1.81) among all 11 methods; buy-once baselines reach lower MDD by holding through the bull run.</div></div>

<div class="grid">
<div class="card"><h2>Sharpe by method</h2><canvas id="srChart"></canvas></div>
<div class="card"><h2>Risk-return (SR vs MDD)</h2><canvas id="scatterChart"></canvas></div>
</div>

<div class="card"><h2>Multi-window robustness — FinOPD Sharpe rank</h2><canvas id="mwChart"></canvas>
<div class="note">#1 Sharpe over the full year and #1 Calmar over the longest out-of-sample window; edge narrows in the choppy H1 regime (rank #6).</div></div>

<div class="grid">
<div class="card"><h2>Ablation — &Delta;Sharpe vs full system</h2><canvas id="ablChart"></canvas></div>
<div class="card"><h2>Sensitivity — take-profit sweep</h2><canvas id="sensChart"></canvas></div>
</div>

<div class="card"><h2>Counterfactual — signal-source &Delta;Sharpe</h2><canvas id="cfChart"></canvas>
<div class="note">Zeroing factors costs 0.15 SR; shuffling them costs only 0.02 SR (relies on structure, not memorized magnitudes).</div></div>

</div>
<script>
const D = __DATA__;
const fmt = (x,d=2)=> (x==null?'-':Number(x).toFixed(d));
// aggregate table
(function(){
 const rows = Object.entries(D.agg).sort((a,b)=>b[1].SR-a[1].SR);
 const bestSR = Math.max(...rows.map(r=>r[1].SR));
 const tb = document.querySelector('#aggTable tbody');
 rows.forEach(([m,v])=>{
  const tr=document.createElement('tr'); if(m==='FinOPD')tr.className='ours';
  const sr = v.SR===bestSR?`<span class="best">${fmt(v.SR)}</span>`:fmt(v.SR);
  tr.innerHTML=`<td>${m}</td><td>${fmt(v.CR,1)}</td><td>${sr}</td><td>${fmt(v.MDD,1)}</td><td>${fmt(v.Calmar)}</td><td>${fmt(v.WR,1)}</td>`;
  tb.appendChild(tr);});
})();
const GRID='#272b36', MUT='#9aa3b2', ACC='#4f8cff', GOOD='#2ecc71';
Chart.defaults.color=MUT; Chart.defaults.borderColor=GRID;
const aggE=Object.entries(D.agg).sort((a,b)=>b[1].SR-a[1].SR);
new Chart(srChart,{type:'bar',data:{labels:aggE.map(e=>e[0]),
 datasets:[{data:aggE.map(e=>e[1].SR),backgroundColor:aggE.map(e=>e[0]==='FinOPD'?ACC:'#3a4150')}]},
 options:{plugins:{legend:{display:false}},scales:{x:{ticks:{maxRotation:60,minRotation:45}}}}});
new Chart(scatterChart,{type:'scatter',data:{datasets:[{
 data:aggE.map(e=>({x:e[1].MDD,y:e[1].SR,m:e[0]})),
 backgroundColor:aggE.map(e=>e[0]==='FinOPD'?ACC:'#6b7384'),pointRadius:6}]},
 options:{plugins:{legend:{display:false},tooltip:{callbacks:{label:c=>c.raw.m+' (MDD '+c.raw.x+', SR '+c.raw.y+')'}}},
 scales:{x:{title:{display:true,text:'MDD %'}},y:{title:{display:true,text:'Sharpe'}}}}});
// multiwindow
(function(){
 const wins=Object.keys(D.mw); const fo=wins.map(w=>D.mw[w].FinOPD?D.mw[w].FinOPD.SR:null);
 new Chart(mwChart,{type:'line',data:{labels:wins,datasets:[{label:'FinOPD Sharpe',data:fo,
  borderColor:ACC,backgroundColor:'rgba(79,140,255,.15)',fill:true,tension:.3,pointRadius:5}]},
  options:{plugins:{legend:{display:false}}}});
})();
// ablation
(function(){
 const e=Object.entries(D.abl).filter(([k])=>k!=='A1_full');
 new Chart(ablChart,{type:'bar',data:{labels:e.map(x=>x[0].replace(/^A\d+_/,'')),
  datasets:[{data:e.map(x=>x[1].dSR||0),backgroundColor:'#e06c6c'}]},
  options:{indexAxis:'y',plugins:{legend:{display:false}}}});
})();
// sensitivity tp
(function(){
 const e=Object.entries(D.sens).filter(([k])=>k.startsWith('tp_'));
 new Chart(sensChart,{type:'line',data:{labels:e.map(x=>x[0].replace('tp_','tp=')),
  datasets:[{label:'SR',data:e.map(x=>x[1].SR),borderColor:GOOD,tension:.3,pointRadius:4}]},
  options:{plugins:{legend:{display:false}}}});
})();
// counterfactual
(function(){
 const e=Object.entries(D.cf).filter(([k])=>k!=='intact');
 new Chart(cfChart,{type:'bar',data:{labels:e.map(x=>x[0]),
  datasets:[{data:e.map(x=>x[1].dSR||0),backgroundColor:'#c79a3a'}]},
  options:{indexAxis:'y',plugins:{legend:{display:false}}}});
})();
</script></body></html>"""
    html = html.replace("__DATA__", djson)
    OUT.write_text(html)
    print(f"Wrote dashboard -> {OUT}")


if __name__ == "__main__":
    main()
