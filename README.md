# Rise — AI Service (FastAPI)

This is the AI layer only. You run this; your backend dev calls it over HTTP and gets JSON back. Nothing here touches auth, payments, persistence, or app logic — that's their job, not yours.

## Setup

```bash
cd rise-ai-fastapi
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Open `.env` and paste your real key:

```
ANTHROPIC_API_KEY=sk-ant-your-real-key-here
```

Run it:

```bash
uvicorn app.main:app --reload --port 8000
```

Check it's alive: `http://localhost:8000/health`

Interactive docs (auto-generated, hand this URL to your backend dev — it shows every field, every endpoint, live "Try it out" buttons): `http://localhost:8000/docs`

## Which API / model

Just one: **Anthropic's Claude API**, one key, in `.env`. Default model is `claude-haiku-4-5-20251001` ($1/$5 per million tokens) — fast and cheap, which fits these short 80-word card responses. Set `ANTHROPIC_MODEL=claude-sonnet-4-6` in `.env` if you want richer language for $3/$15 instead. No other API needed.

## What your backend dev needs to know

Give them this: every endpoint is `POST http://<your-host>:8000/ai/<name>`, body is JSON, response is JSON. Full field-level contract is in `app/models.py` and live at `/docs`. They don't need to read your prompt code at all.

```
POST /ai/context
POST /ai/coach
POST /ai/focus
POST /ai/plan
POST /ai/intervention
POST /ai/future-me
POST /ai/recap
POST /ai/music
POST /ai/reward
POST /ai/memory/extract
POST /ai/goals/progress

GET  /ai/memory/{user_id}   (read stored memories — convenience, not in original spec)
GET  /ai/cost               (dev cost visibility)
POST /ai/coach/stream       (SSE streaming example — same pattern works for any endpoint)
```

Every endpoint optionally accepts `coach_personality` (`sweet` | `strict` | `sarcastic` | `ceo` | `therapeutic`, default `sweet`), and either `user_id` (auto-loads stored memories) or an inline `memories` array.

Example call:
```bash
curl -X POST http://localhost:8000/ai/coach \
  -H "Content-Type: application/json" \
  -d '{"mood":"stressed","energy":"low","goals":["Read more"],"coach_personality":"sweet"}'
```

## Project layout

```
app/
  main.py              <- all 11 endpoints, FastAPI app
  models.py             <- request schemas (the contract — share this file or /docs with your backend dev)
  prompts/
    base_prompt.py       <- global rules: emotional arc, 80-word cap, JSON-only
    personalities.py     <- 5 tone presets
    endpoint_prompts.py  <- per-endpoint instructions + JSON schema
  services/
    claude_client.py     <- Claude API calls: retries, streaming, cost tracking
    memory_store.py       <- in-memory personalization facts (swap for DB later)
```

## What's implemented

- Prompt templates (✅ `prompts/`)
- Memory injection (✅ every endpoint pulls `user_id`'s memories or accepts inline `memories`)
- Personality system (✅ 5 tones, swappable per-request)
- Structured outputs (✅ strict JSON schema per endpoint, defensively parsed)
- Streaming (✅ `/ai/coach/stream` as a working example; same pattern applies to any endpoint)
- Token optimization (✅ short max_tokens caps matched to the 80-word limit, Haiku as default)
- Retries (✅ exponential backoff on rate limits / transient errors only)
- Cost tracking (✅ `/ai/cost`, plus `_meta.usage` on every response)
- No auth, no DB, no payments, no frontend — exactly as scoped

## Known limitation (intentional)

Memory is a Python dict in RAM — resets if the process restarts. That's deliberate, since DB management was explicitly out of scope. Swap the two functions in `memory_store.py` for real DB calls whenever you're ready; nothing else changes.
