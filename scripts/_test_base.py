import base64, time, requests, sys

img = 'data/opd_train_v2/charts/AAPL_2018-08-27.png'
b64 = base64.b64encode(open(img, 'rb').read()).decode()
prompt = ('Analyze this candlestick chart and predict 5-day direction. '
          'Output ONLY JSON: {"direction":"bullish/bearish/neutral","confidence":0.0-1.0,"action":"buy/sell/hold"}')
msg = [{"role": "user", "content": [
    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
    {"type": "text", "text": prompt},
]}]
port = sys.argv[1] if len(sys.argv) > 1 else "8001"
t = time.time()
r = requests.post(f"http://localhost:{port}/v1/chat/completions",
                  json={"model": "base", "messages": msg, "max_tokens": 80, "temperature": 0,
                        "extra_body": {"enable_thinking": False}},
                  timeout=180)
dt = time.time() - t
print(f"latency: {dt:.1f}s")
print("resp:", r.json()["choices"][0]["message"]["content"][:250])
