import requests
r = requests.get("https://hub-api.opengradient.ai/api/v0/models/og-1hr-volatility-ethusdt/files?extension=onnx")
print(r.status_code)
print(r.text[:200])