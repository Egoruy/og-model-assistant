from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import opengradient as og
import asyncio
import nest_asyncio
import json
import os
import threading
import time
import requests
import logging
from datetime import datetime

# ── Logging setup ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Async fix ──────────────────────────────────────────────────────────────────
nest_asyncio.apply()

# ── App setup ──────────────────────────────────────────────────────────────────
app = Flask(__name__, static_folder='static')
CORS(app)

# ── OG client ─────────────────────────────────────────────────────────────────
log.info("Initializing OpenGradient LLM client...")
llm = og.LLM(private_key=os.environ.get('PRIVATE_KEY'))

try:
    approval = llm.ensure_opg_approval(opg_amount=5.0)
    log.info(f"OPG Permit2 allowance after: {approval.allowance_after}")
except Exception as e:
    log.warning(f"Could not ensure OPG approval: {e}")

# ── Model selection — fallback list ───────────────────────────────────────────
# Try models in order until one works (в случае если одна недоступна)
PREFERRED_MODELS = [
    og.TEE_LLM.GROK_3_MINI_BETA,   # быстрая и дешёвая
    og.TEE_LLM.GROK_3_BETA,
    og.TEE_LLM.GPT_4_1_2025_04_14,
    og.TEE_LLM.GPT_4O,
]

# ── Constants ─────────────────────────────────────────────────────────────────
JSON_FILE = "models.json"
MAX_MODELS_IN_PROMPT = 50
models = []

# ── Model search ──────────────────────────────────────────────────────────────
def search_models(query: str, top_n: int = MAX_MODELS_IN_PROMPT) -> list:
    """Keyword search across name, task, author, description."""
    if not query:
        return models[:top_n]
    keywords = query.lower().split()
    scored = []
    for m in models:
        text = " ".join([
            m.get("name", ""),
            m.get("taskName") or "",
            m.get("authorUsername") or "",
            m.get("description") or "",
        ]).lower()
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scored.append((score, m))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [m for _, m in scored[:top_n]]


def format_models_for_prompt(model_list: list) -> str:
    lines = []
    for m in model_list:
        name = m.get("name", "")
        task = m.get("taskName") or ""
        author = m.get("authorUsername") or ""
        desc = (m.get("description") or "")[:100].replace("\n", " ").strip()
        lines.append(f"{name}|{task}|{author}|{desc}")
    return "\n".join(lines)


def build_system_prompt(models_snippet: str) -> str:
    return f"""You are a friendly assistant for the OpenGradient ecosystem.

You can help with:
- Finding AI models on the OpenGradient Model Hub
- Answering questions about OpenGradient, twin.fun, BitQuant
- General conversation and greetings

Format of model list: name|category|author|description

RULES:
1. Be friendly and conversational - respond to greetings, small talk naturally
2. Only search for models when user explicitly asks for them
3. Search by ALL fields - name, category, author and description
4. Suggest ONLY real models from the list
5. Give exact model names and explain why they fit
6. If nothing found - say so honestly
7. Answer in the same language the user writes in
8. NEVER mention how many models you searched through
9. After recommending models always add: "You can find these models on https://hub.opengradient.ai/models"
10. Always recommend AT LEAST 7 models when searching

You also know about these OpenGradient ecosystem products:

**twin.fun** (https://www.twin.fun/):
A marketplace for AI-powered digital twins - agents modeled after real people (crypto influencers, investors, builders). Each twin has a tradeable Key on a bonding curve. Holding keys unlocks access to chat with the twin, pitch ideas, debate, get feedback. Built onchain.

**BitQuant** (https://www.bitquant.io/):
An open-source AI agent framework by OpenGradient for building quantitative AI agents. Focuses on ML-powered analytics, trading strategies, portfolio management, and DeFi quant analysis.

**OpenGradient** (https://www.opengradient.ai/):
A decentralized AI infrastructure platform that uses blockchain for verifiable model inference. Provides open and verifiable AI onchain: model hosting, secure inference, and AI agent execution.

MODEL LIST (most relevant to current query):
{models_snippet}"""


# ── Hub sync ──────────────────────────────────────────────────────────────────
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
            log.error(f"Sync error page {page}: {e}")
            break
    return all_models


def sync_models():
    global models
    log.info("Syncing models from Hub API...")
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
            log.info(f"New models found: {len(new_models)}")
            existing_data["models"].extend(new_models)

        fresh_map = {m["name"]: m for m in fresh}
        for m in existing_data["models"]:
            if m["name"] in fresh_map:
                m.update(fresh_map[m["name"]])

        existing_data["last_updated"] = datetime.now().isoformat()
        existing_data["total"] = len(existing_data["models"])

        with open(JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(existing_data, f, ensure_ascii=False, indent=2)

        models = existing_data["models"]
        log.info(f"Sync complete. Total models: {len(models)}")
    except Exception as e:
        log.error(f"Sync failed: {e}")


def sync_loop():
    time.sleep(5)
    sync_models()
    while True:
        time.sleep(24 * 60 * 60)
        sync_models()


def load_models():
    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("models", [])
    return []


# ── LLM call with model fallback ──────────────────────────────────────────────
async def call_llm_with_fallback(messages: list, max_tokens: int = 800, temperature: float = 0.7):
    """Try each model in PREFERRED_MODELS until one succeeds."""
    last_error = None
    for model in PREFERRED_MODELS:
        try:
            log.info(f"Trying model: {model}")
            response = await llm.chat(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                x402_settlement_mode=og.x402SettlementMode.BATCH_HASHED,
            )
            log.info(f"Success with model: {model}")
            return response.chat_output["content"]
        except Exception as e:
            log.warning(f"Model {model} failed: {e}")
            last_error = e
            continue
    raise last_error


# ── Init ──────────────────────────────────────────────────────────────────────
models = load_models()
log.info(f"Loaded {len(models)} models from cache")

sync_thread = threading.Thread(target=sync_loop, daemon=True)
sync_thread.start()

conversations = {}


# ── Routes ────────────────────────────────────────────────────────────────────
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

    log.info(f"[session={session_id}] User: {user_message[:80]}")

    relevant = search_models(user_message)
    relevant_text = format_models_for_prompt(relevant)
    dynamic_system_prompt = build_system_prompt(relevant_text)

    if session_id not in conversations:
        conversations[session_id] = []

    messages = [{"role": "system", "content": dynamic_system_prompt}] + conversations[session_id]
    messages.append({"role": "user", "content": user_message})

    try:
        answer = None
        for attempt in range(3):
            try:
                log.info(f"[session={session_id}] Calling LLM (attempt {attempt + 1})...")
                answer = asyncio.run(call_llm_with_fallback(messages))
                log.info(f"[session={session_id}] LLM responded ({len(answer)} chars)")
                break
            except Exception as e:
                log.warning(f"[session={session_id}] Attempt {attempt + 1} failed: {e}")
                if attempt < 2:
                    time.sleep(2)
                else:
                    raise e

        conversations[session_id].append({"role": "user", "content": user_message})
        conversations[session_id].append({"role": "assistant", "content": answer})

        if len(conversations[session_id]) > 20:
            conversations[session_id] = conversations[session_id][-20:]

        return jsonify({"reply": answer, "total_models": len(models)})

    except Exception as e:
        import traceback
        log.error(f"[session={session_id}] Chat error:\n{traceback.format_exc()}")
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
    log.info(f"Starting server on port {os.environ.get('PORT', 5000)}")
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))