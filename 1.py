import requests
import json
from datetime import datetime

JSON_FILE = "models.json"

with open(JSON_FILE, "r", encoding="utf-8") as f:
    existing_data = json.load(f)

existing_names = {m["name"] for m in existing_data["models"]}

all_fresh = []
page = 0
while True:
    r = requests.get(f"https://hub-api.opengradient.ai/api/v0/models/?page={page}&limit=100")
    data = r.json()
    batch = data.get("models", data) if isinstance(data, dict) else data
    if not batch:
        break
    all_fresh.extend(batch)
    if len(batch) < 100:
        break
    page += 1

new_models = [m for m in all_fresh if m["name"] not in existing_names]
print(f"Новых моделей: {len(new_models)}")

existing_data["models"].extend(new_models)
existing_data["last_updated"] = datetime.now().isoformat()
existing_data["total"] = len(existing_data["models"])

with open(JSON_FILE, "w", encoding="utf-8") as f:
    json.dump(existing_data, f, ensure_ascii=False, indent=2)

print(f"✅ Готово! Всего: {existing_data['total']}")