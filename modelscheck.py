import json

with open("models.json", "r", encoding="utf-8") as f:
    data = json.load(f)

models = data["models"]

# Смотрим все ключи первой модели
print("Ключи в модели:")
print(list(models[0].keys()))

# И пару примеров
print("\nПример модели:")
import pprint
pprint.pprint(models[0])