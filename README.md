# OpenGradient Model Hub Assistant

A conversational AI assistant for discovering and exploring models on the [OpenGradient Model Hub](https://hub.opengradient.ai/models). Powered by verifiable on-chain inference via the OpenGradient SDK.

**Live demo:** https://opengradient-assistant.up.railway.app/

---

## Features

- Natural language model search across 1000+ models on the OpenGradient Hub
- Context about the OpenGradient ecosystem (twin.fun, BitQuant)
- Verifiable inference via TEE using `og.TEE_LLM.GROK_4_FAST`
- Automatic daily model sync from the Hub API
- Multi-turn conversation with session support

---

## Tech Stack

- **Backend:** Python, Flask, OpenGradient SDK
- **Frontend:** Vanilla HTML/CSS/JS (single file)
- **Inference:** OpenGradient TEE LLM (on-chain, verifiable)
- **Deployment:** Railway

---

## Setup

### Prerequisites

- Python 3.9+
- An OpenGradient wallet private key
- OPG tokens on Base Sepolia (get from the [faucet](https://hub.opengradient.ai/faucet))

### Install

```bash
git clone https://github.com/Egoruy/og-model-assistant.git
cd og-model-assistant
pip install -r requirements.txt
```

### Configure

Create a `.env` file or set the environment variable:

```bash
export PRIVATE_KEY=your_wallet_private_key_here
```

> ⚠️ Never commit your private key. It is read from the environment at runtime.

### Run

```bash
python app.py
```

The app will be available at `http://localhost:5000`.

On first start, it loads `models.json` (if present) and kicks off a background sync from the Hub API. Sync runs again every 24 hours automatically.

---

## Deployment (Railway)

1. Push repo to GitHub
2. Create a new Railway project → Deploy from GitHub repo
3. Add environment variable `PRIVATE_KEY` in Railway settings
4. Railway uses the `Procfile` automatically: `web: python app.py`

> **Note:** `models.json` is not persisted across Railway deploys (ephemeral filesystem). On each fresh deploy the app fetches all models from the Hub API on first sync. This takes ~30 seconds.

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Chat UI |
| POST | `/api/chat` | Send a message, get a reply |
| GET | `/api/stats` | Model count, categories, last sync time |
| POST | `/api/sync` | Trigger a manual model sync |

### POST `/api/chat`

```json
{
  "session_id": "user-123",
  "message": "Find me a text classification model"
}
```

Response:
```json
{
  "reply": "Here are some text classification models...",
  "total_models": 1042
}
```

---

## Project Structure

```
og-model-assistant/
├── app.py              # Flask backend, sync logic, OG SDK integration
├── static/
│   └── index.html      # Single-page chat UI
├── models.json         # Cached model database (gitignored, auto-generated)
├── requirements.txt
├── Procfile            # Railway deployment config
└── README.md
```

---

## How It Works

1. On startup, models are loaded from `models.json` (local cache)
2. A background thread syncs new/updated models from the Hub API every 24 hours
3. The model list is injected into the system prompt of the LLM
4. User messages are sent to `og.TEE_LLM.GROK_4_FAST` via the OpenGradient SDK
5. Inference is executed on-chain inside a Trusted Execution Environment (TEE)
6. Responses are streamed back to the frontend

---

## License

MIT
