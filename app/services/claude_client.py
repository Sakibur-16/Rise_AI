"""
Provider-agnostic AI client.

Switch providers by setting AI_PROVIDER in .env:
  anthropic | openai | google | groq | mistral | together
"""

import os
import re
import json
import asyncio
from typing import AsyncIterator

# ── Config ────────────────────────────────────────────────────────────────────
PROVIDER     = os.getenv("AI_PROVIDER", "anthropic").lower()
MAX_RETRIES  = int(os.getenv("AI_MAX_RETRIES", "3"))
BASE_BACKOFF = 0.4

# ── Per-provider defaults ─────────────────────────────────────────────────────
_DEFAULTS = {
    "anthropic": {
        "key_env":   "ANTHROPIC_API_KEY",
        "model_env": "ANTHROPIC_MODEL",
        "model":     "claude-haiku-4-5-20251001",
    },
    "openai": {
        "key_env":   "OPENAI_API_KEY",
        "model_env": "OPENAI_MODEL",
        "model":     "gpt-4o-mini",
    },
    "google": {
        "key_env":   "GOOGLE_API_KEY",
        "model_env": "GOOGLE_MODEL",
        "model":     "gemini-2.0-flash",
    },
    "groq": {
        "key_env":   "GROQ_API_KEY",
        "model_env": "GROQ_MODEL",
        "model":     "llama-3.3-70b-versatile",
    },
    "mistral": {
        "key_env":   "MISTRAL_API_KEY",
        "model_env": "MISTRAL_MODEL",
        "model":     "mistral-small-latest",
    },
    "together": {
        "key_env":   "TOGETHER_API_KEY",
        "model_env": "TOGETHER_MODEL",
        "model":     "meta-llama/Llama-3.3-70B-Instruct-Turbo",
    },
}

if PROVIDER not in _DEFAULTS:
    raise RuntimeError(
        f"[AI] Unknown AI_PROVIDER='{PROVIDER}'. "
        f"Valid values: {', '.join(_DEFAULTS)}"
    )

_cfg = _DEFAULTS[PROVIDER]
_api_key     = os.getenv(_cfg["key_env"])
DEFAULT_MODEL = os.getenv(_cfg["model_env"], _cfg["model"])

if not _api_key:
    print(f"[FATAL] {_cfg['key_env']} is missing. Set it in your .env file.")

# ── Pricing per million tokens (USD) ─────────────────────────────────────────
PRICING = {
    # Anthropic
    "claude-haiku-4-5-20251001":  {"input": 1.0,  "output": 5.0},
    "claude-sonnet-4-6":          {"input": 3.0,  "output": 15.0},
    "claude-opus-4-8":            {"input": 5.0,  "output": 25.0},
    # OpenAI
    "gpt-4o-mini":                {"input": 0.15, "output": 0.6},
    "gpt-4o":                     {"input": 2.5,  "output": 10.0},
    # Google
    "gemini-2.0-flash":           {"input": 0.1,  "output": 0.4},
    "gemini-1.5-pro":             {"input": 1.25, "output": 5.0},
    # Groq (estimate)
    "llama-3.3-70b-versatile":    {"input": 0.59, "output": 0.79},
    # Mistral
    "mistral-small-latest":       {"input": 0.1,  "output": 0.3},
    "mistral-large-latest":       {"input": 2.0,  "output": 6.0},
}

_cost_ledger = {
    "total_input_tokens": 0,
    "total_output_tokens": 0,
    "total_cost_usd": 0.0,
    "call_count": 0,
}


# ── Helpers ───────────────────────────────────────────────────────────────────
def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    rates = PRICING.get(model, {"input": 0.0, "output": 0.0})
    return (input_tokens / 1_000_000) * rates["input"] + (output_tokens / 1_000_000) * rates["output"]


def _record_usage(model: str, input_tokens: int, output_tokens: int) -> dict:
    cost = _estimate_cost(model, input_tokens, output_tokens)
    _cost_ledger["total_input_tokens"] += input_tokens
    _cost_ledger["total_output_tokens"] += output_tokens
    _cost_ledger["total_cost_usd"] += cost
    _cost_ledger["call_count"] += 1
    return {"input_tokens": input_tokens, "output_tokens": output_tokens, "cost_usd": round(cost, 6)}


def get_cost_ledger() -> dict:
    return {**_cost_ledger, "total_cost_usd": round(_cost_ledger["total_cost_usd"], 6)}


def _safe_parse_json(text: str) -> dict | None:
    if not text:
        return None
    cleaned = re.sub(r"```json\s*|```\s*", "", text).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", cleaned)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return None
        return None


class AIServiceError(Exception):
    def __init__(self, message: str, status_code: int = 500, code: str = "AI_SERVICE_ERROR"):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


# ── Provider implementations ──────────────────────────────────────────────────

async def _call_anthropic(system_prompt, user_prompt, model, max_tokens, temperature):
    from anthropic import AsyncAnthropic, APIStatusError, APIConnectionError

    client = AsyncAnthropic(api_key=_api_key)

    def _retryable(err):
        if isinstance(err, APIConnectionError):
            return True
        return isinstance(err, APIStatusError) and err.status_code in (429, 500, 503, 529)

    last_err = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = await client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            raw = "".join(b.text for b in response.content if b.type == "text")
            usage = _record_usage(model, response.usage.input_tokens or 0, response.usage.output_tokens or 0)
            return raw, usage
        except Exception as err:
            last_err = err
            if not _retryable(err) or attempt == MAX_RETRIES:
                break
            await asyncio.sleep(BASE_BACKOFF * (2 ** attempt))
    raise AIServiceError(str(last_err))


async def _stream_anthropic(system_prompt, user_prompt, model, max_tokens, temperature):
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(api_key=_api_key)
    async with client.messages.stream(
        model=model, max_tokens=max_tokens, temperature=temperature,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    ) as stream:
        async for delta in stream.text_stream:
            yield delta
        final = await stream.get_final_message()
        _record_usage(model, final.usage.input_tokens or 0, final.usage.output_tokens or 0)


async def _call_openai_compat(system_prompt, user_prompt, model, max_tokens, temperature, base_url=None):
    from openai import AsyncOpenAI

    kwargs = {"api_key": _api_key}
    if base_url:
        kwargs["base_url"] = base_url

    client = AsyncOpenAI(**kwargs)
    response = await client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    raw = response.choices[0].message.content or ""
    usage = response.usage
    recorded = _record_usage(model, usage.prompt_tokens or 0, usage.completion_tokens or 0)
    return raw, recorded


async def _stream_openai_compat(system_prompt, user_prompt, model, max_tokens, temperature, base_url=None):
    from openai import AsyncOpenAI

    kwargs = {"api_key": _api_key}
    if base_url:
        kwargs["base_url"] = base_url

    client = AsyncOpenAI(**kwargs)
    stream = await client.chat.completions.create(
        model=model, max_tokens=max_tokens, temperature=temperature,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        stream=True,
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


async def _call_google(system_prompt, user_prompt, model, max_tokens, temperature):
    import google.generativeai as genai

    genai.configure(api_key=_api_key)
    g_model = genai.GenerativeModel(
        model_name=model,
        system_instruction=system_prompt,
    )
    response = await g_model.generate_content_async(
        user_prompt,
        generation_config=genai.GenerationConfig(max_output_tokens=max_tokens, temperature=temperature),
    )
    raw = response.text or ""
    in_tok  = response.usage_metadata.prompt_token_count or 0
    out_tok = response.usage_metadata.candidates_token_count or 0
    usage = _record_usage(model, in_tok, out_tok)
    return raw, usage


async def _stream_google(system_prompt, user_prompt, model, max_tokens, temperature):
    import google.generativeai as genai

    genai.configure(api_key=_api_key)
    g_model = genai.GenerativeModel(model_name=model, system_instruction=system_prompt)
    async for chunk in await g_model.generate_content_async(
        user_prompt,
        generation_config=genai.GenerationConfig(max_output_tokens=max_tokens, temperature=temperature),
        stream=True,
    ):
        if chunk.text:
            yield chunk.text


# ── Provider routing ──────────────────────────────────────────────────────────

_OPENAI_COMPAT_BASES = {
    "groq":     "https://api.groq.com/openai/v1",
    "mistral":  "https://api.mistral.ai/v1",
    "together": "https://api.together.xyz/v1",
}


async def _dispatch_call(system_prompt, user_prompt, model, max_tokens, temperature):
    if PROVIDER == "anthropic":
        return await _call_anthropic(system_prompt, user_prompt, model, max_tokens, temperature)
    if PROVIDER == "google":
        return await _call_google(system_prompt, user_prompt, model, max_tokens, temperature)
    # openai + compat providers
    base_url = os.getenv("OPENAI_BASE_URL") or _OPENAI_COMPAT_BASES.get(PROVIDER)
    return await _call_openai_compat(system_prompt, user_prompt, model, max_tokens, temperature, base_url)


async def _dispatch_stream(system_prompt, user_prompt, model, max_tokens, temperature):
    if PROVIDER == "anthropic":
        async for chunk in _stream_anthropic(system_prompt, user_prompt, model, max_tokens, temperature):
            yield chunk
        return
    if PROVIDER == "google":
        async for chunk in _stream_google(system_prompt, user_prompt, model, max_tokens, temperature):
            yield chunk
        return
    base_url = os.getenv("OPENAI_BASE_URL") or _OPENAI_COMPAT_BASES.get(PROVIDER)
    async for chunk in _stream_openai_compat(system_prompt, user_prompt, model, max_tokens, temperature, base_url):
        yield chunk


# ── Public API ────────────────────────────────────────────────────────────────

async def call_claude_json(
    system_prompt: str,
    user_prompt: str,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 400,
    temperature: float = 0.7,
) -> dict:
    """Non-streaming call. Returns {data, usage, model, raw}."""
    try:
        raw, usage = await _dispatch_call(system_prompt, user_prompt, model, max_tokens, temperature)
    except AIServiceError:
        raise
    except Exception as err:
        raise AIServiceError(str(err))

    parsed = _safe_parse_json(raw)
    if parsed is None:
        raise AIServiceError("AI returned non-JSON or malformed JSON.", status_code=502, code="PARSE_ERROR")

    return {"data": parsed, "usage": usage, "model": model, "raw": raw}


async def stream_claude(
    system_prompt: str,
    user_prompt: str,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 400,
    temperature: float = 0.7,
) -> AsyncIterator[str]:
    """Streaming call. Yields text deltas as they arrive."""
    try:
        async for chunk in _dispatch_stream(system_prompt, user_prompt, model, max_tokens, temperature):
            yield chunk
    except AIServiceError:
        raise
    except Exception as err:
        raise AIServiceError(str(err))
