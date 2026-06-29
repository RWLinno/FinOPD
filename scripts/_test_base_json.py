import base64, time, requests, sys
img='data/opd_train_v2/charts/AAPL_2018-08-27.png'
b64=base64.b64encode(open(img,'rb').read()).decode()
sys_p='You are a financial chart analyst. Output ONLY one line of compact JSON, no thinking, no markdown: {"direction":"bullish|bearish|neutral","confidence":0.0,"action":"buy|sell|hold"}'
msg=[{"role":"system","content":sys_p},
     {"role":"user","content":[{"type":"image_url","image_url":{"url":f"data:image/png;base64,{b64}"}},
      {"type":"text","text":"Predict 5-day direction. JSON only."}]}]
t=time.time()
r=requests.post("http://localhost:8002/v1/chat/completions",
  json={"model":"base","messages":msg,"max_tokens":100,"temperature":0,"extra_body":{"enable_thinking":False}},timeout=110)
print(f"latency {time.time()-t:.1f}s")
print("resp:", r.json()["choices"][0]["message"]["content"][:200])
