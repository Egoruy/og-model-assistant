from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import opengradient as og
import json
import os
import threading
import time
import requests
from datetime import datetime

app = Flask(__name__, static_folder='static')
CORS(app)

client = og.init(
    private_key="0x2f68df46eeec5481f1c73cb6fbd49cafd215953533aa238287b7f6a7dd955c04"
)

JSON_FILE = "models.json"

def fetch_all_from_api():
    all_models = []
    page = 0
    limit = 100
    while True:
        try:
            url = f"https://hub-api.opengradient.ai/api/v0/models/?page={page}&limit={limit}"
            r = requests.get(url, timeout=10)
            data = r.json()
            batch = data.get("models", data) if isinstance(data, dict) else data
            if not batch:
                break
            all_models.extend(batch)
            if len(batch) < limit:
                break
            page += 1
        except Exception as e:
            print(f"Sync error page {page}: {e}")
            break
    return all_models

def sync_models():
    global models, models_text, SYSTEM_PROMPT
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Syncing models...")
    try:
        if os.path.exists(JSON_FILE):
            with open(JSON_FILE, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
        else:
            existing_data = {"models": [], "last_updated": None, "total": 0}

        existing_names = {m["name"] for m in existing_data["models"]}
        fresh = fetch_all_from_api()
        new_models = [m for m in fresh if m["name"] not in existing_names]

        if new_models:
            print(f"  New models: {len(new_models)}")
            existing_data["models"].extend(new_models)
        else:
            print(f"  No new models.")

        existing_data["last_updated"] = datetime.now().isoformat()
        existing_data["total"] = len(existing_data["models"])

        with open(JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(existing_data, f, ensure_ascii=False, indent=2)

        models = existing_data["models"]
        models_text = format_models_for_prompt(models)
        SYSTEM_PROMPT = build_system_prompt(models, models_text)
        print(f"  Total models: {len(models)}")
    except Exception as e:
        print(f"  Sync failed: {e}")

def sync_loop():
    while True:
        time.sleep(24 * 60 * 60)
        sync_models()

def load_models():
    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("models", [])
    return []

def format_models_for_prompt(models):
    lines = []
    for m in models:
        name = m.get("name", "")
        task = m.get("taskName") or ""
        desc = m.get("description") or ""
        author = m.get("authorUsername") or ""
        desc_short = desc[:100].replace("\n", " ").strip()
        lines.append(f"{name}|{task}|{author}|{desc_short}")
    return "\n".join(lines)

def build_system_prompt(models, models_text):
    return f"""You are an assistant for the OpenGradient Model Hub platform.
You have {len(models)} AI models available.

Format: name|category|author|description

RULES:
1. Search by ALL fields - name, category, author and description
2. Suggest ONLY real models from the list
3. Give exact model names
4. Explain why each model fits the request
5. If nothing found - say so honestly
6. Answer in the same language the user writes in
7. NEVER mention how many models you searched through or processed - just give the results directly
8. After recommending models always add at the end: "You can find these models on https://hub.opengradient.ai/models search"
9. Always recommend AT LEAST 7 models per request if possible

You also have knowledge about these OpenGradient ecosystem products:

**twin.fun** (https://www.twin.fun/):
A marketplace for AI-powered digital twins - agents modeled after real people (crypto influencers, investors, builders). Each twin has a tradeable Key on a bonding curve. Holding keys unlocks access to chat with the twin, pitch ideas, debate, get feedback. Built onchain.

**BitQuant** (https://www.bitquant.io/):
An open-source AI agent framework by OpenGradient for building quantitative AI agents. Focuses on ML-powered analytics, trading strategies, portfolio management, and DeFi quant analysis.

MODEL LIST:
{models_text}"""

models = load_models()
models_text = format_models_for_prompt(models)
SYSTEM_PROMPT = build_system_prompt(models, models_text)

sync_thread = threading.Thread(target=sync_loop, daemon=True)
sync_thread.start()

conversations = {}

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    session_id = data.get('session_id', 'default')
    user_message = data.get('message', '')

    if session_id not in conversations:
        conversations[session_id] = [{"role": "system", "content": SYSTEM_PROMPT}]

    conversations[session_id].append({"role": "user", "content": user_message})

    try:
        answer = None
        for attempt in range(3):
            try:
                response = client.llm.chat(
                    model=og.TEE_LLM.GROK_3_MINI_BETA,
                    messages=conversations[session_id],
                    max_tokens=800,
                    temperature=0.7,
                )
                answer = response.chat_output["content"]
                break
            except Exception as e:
                if attempt < 2:
                    time.sleep(2)
                else:
                    raise e
        conversations[session_id].append({"role": "assistant", "content": answer})
        return jsonify({"reply": answer, "total_models": len(models)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/stats')
def stats():
    from collections import Counter
    tasks = Counter(m.get("taskName") for m in models if m.get("taskName"))
    last_sync = None
    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            last_sync = json.load(f).get("last_updated")
    return jsonify({
        "total": len(models),
        "categories": dict(tasks.most_common()),
        "last_updated": last_sync
    })

@app.route('/api/sync', methods=['POST'])
def manual_sync():
    threading.Thread(target=sync_models, daemon=True).start()
    return jsonify({"status": "sync started"})

if __name__ == '__main__':
    print(f"Loaded {len(models)} models")
    print(f"Auto-sync every 24 hours")
    app.run(debug=True, port=5000)
