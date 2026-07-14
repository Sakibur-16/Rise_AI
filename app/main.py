"""
Rise AI Microservice — FastAPI entrypoint.

This is the entire AI layer. Your backend (Node/Express, etc.) calls these
endpoints over HTTP and gets card-ready JSON back. Nothing here does auth,
payments, persistence, or business logic — that's your backend's job.

Run:
    python app/main.py
  OR:
    uvicorn app.main:app --reload --port 8000

Docs: http://127.0.0.1:8000/docs
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse

from app.models import (
    # requests
    ContextRequest, CoachRequest, FocusRequest, PlanRequest,
    InterventionRequest, FutureMeRequest, RecapRequest,
    MusicRequest, RewardRequest, GoalsProgressRequest, MemoryExtractRequest,
    ChatRequest,
    # responses
    ContextResponse, CoachResponse, FocusResponse, PlanResponse,
    InterventionResponse, FutureMeResponse, RecapResponse,
    MusicResponse, RewardResponse, GoalsProgressResponse, MemoryExtractResponse,
    HealthResponse, CostResponse, MemoryReadResponse,
    ChatResponse,
)
from app.prompts.base_prompt import build_system_prompt
from app.prompts.endpoint_prompts import ENDPOINT_PROMPTS
from app.services.claude_client import call_claude_json, stream_claude, get_cost_ledger, AIServiceError
from app.services.memory_store import get_memories, add_memories

# ── App ───────────────────────────────────────────────────────────────────────

tags_metadata = [
    {"name": "System",     "description": "Health check and usage/cost visibility."},
    {"name": "Core",       "description": "Context snapshot and coach card — the two most-used endpoints."},
    {"name": "Planning",   "description": "Focus tasks and day planning."},
    {"name": "Wellbeing",  "description": "Interventions, future projection, and evening recap."},
    {"name": "Engagement", "description": "Music suggestions, reward progress, and goal tracking."},
    {"name": "Memory",     "description": "Read and extract durable user memories for personalisation."},
]

app = FastAPI(
    title="Rise AI Microservice",
    description=(
        "AI-only backend for the Rise app.\n\n"
        "## Auto-detection\n"
        "Every endpoint supports a `message` field. When provided, the AI uses it to:\n"
        "- **Infer mood** if `mood` is not explicitly set\n"
        "- **Infer energy** if `energy` is not set\n"
        "- **Choose the best personality** when `coach_personality` is `auto`\n\n"
        "The chosen/detected values are always returned as `detected_mood` and "
        "`detected_personality` so your frontend can cache and display them.\n\n"
        "## Personalities\n"
        "| Key | Style |\n"
        "|---|---|\n"
        "| `auto` | AI picks from message tone |\n"
        "| `sweet` | Warm, nurturing best-friend |\n"
        "| `strict` | Direct, no-nonsense coach |\n"
        "| `sarcastic` | Witty, teasing but caring |\n"
        "| `ceo` | Strategic, results-driven |\n"
        "| `therapeutic` | Calm, validating, trauma-informed |"
    ),
    version="1.0.0",
    openapi_tags=tags_metadata,
)


# ── Shared helpers ────────────────────────────────────────────────────────────

def _resolve_memories(req) -> list[str]:
    if req.memories:
        return req.memories
    if req.user_id:
        return get_memories(req.user_id)
    return []


def _maybe(value, fallback: str = "(infer from message above)") -> str:
    return value if value is not None else fallback


async def _run_endpoint(endpoint_key: str, req, user_prompt: str) -> dict:
    config   = ENDPOINT_PROMPTS[endpoint_key]
    memories = _resolve_memories(req)

    personality           = getattr(req, "coach_personality", "auto")
    mood                  = getattr(req, "mood", None)
    energy                = getattr(req, "energy", None)
    needs_mood_detection  = mood is None
    needs_energy_detection = energy is None

    system_prompt = build_system_prompt(
        personality=personality,
        memories=memories,
        extra_instructions=(
            f"{config['instructions']}\n\n"
            f"Return JSON matching EXACTLY this schema (no extra fields):\n{config['schema']}"
        ),
        needs_mood_detection=needs_mood_detection,
        needs_energy_detection=needs_energy_detection,
    )

    try:
        result = await call_claude_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=450,
        )
    except AIServiceError as err:
        raise HTTPException(
            status_code=err.status_code,
            detail={"error": err.code, "message": err.message},
        )

    return {**result["data"], "meta": result["usage"]}


def _build_user_prompt(req, core_lines: list[str]) -> str:
    parts = []
    if getattr(req, "message", None):
        parts.append(f'User\'s message: "{req.message}"')
        parts.append("")
    parts.extend(core_lines)
    return "\n".join(parts)


# ── System ────────────────────────────────────────────────────────────────────

@app.get(
    "/health",
    tags=["System"],
    summary="Health check",
    response_model=HealthResponse,
)
async def health():
    return {"status": "ok", "service": "rise-ai-microservice"}


@app.get(
    "/ai/cost",
    tags=["System"],
    summary="Token & cost usage",
    description="Running token + cost totals since the process started. Resets on restart. Dev visibility only.",
    response_model=CostResponse,
)
async def cost():
    return get_cost_ledger()


# ── Memory ────────────────────────────────────────────────────────────────────

@app.get(
    "/ai/memory/{user_id}",
    tags=["Memory"],
    summary="Read stored memories",
    description="Returns all durable memories stored for a user.",
    response_model=MemoryReadResponse,
)
async def read_memory(user_id: str):
    return {"user_id": user_id, "memories": get_memories(user_id)}


@app.post(
    "/ai/memory/extract",
    tags=["Memory"],
    summary="Extract memories from text",
    description=(
        "Analyses raw user text (chat message, voice transcript, journal entry) and extracts "
        "durable personalisation facts. Extracted memories are stored and returned."
    ),
    response_model=MemoryExtractResponse,
)
async def ai_memory_extract(req: MemoryExtractRequest):
    config = ENDPOINT_PROMPTS["memory/extract"]
    system_prompt = build_system_prompt(
        extra_instructions=(
            f"{config['instructions']}\n\n"
            f"Return JSON matching EXACTLY this schema:\n{config['schema']}"
        ),
    )
    user_prompt = f'Raw input from user:\n"{req.text}"\n\nExtract durable memories, if any.'

    try:
        result = await call_claude_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=300,
        )
    except AIServiceError as err:
        raise HTTPException(
            status_code=err.status_code,
            detail={"error": err.code, "message": err.message},
        )

    data   = result["data"]
    saved  = add_memories(req.user_id, data.get("memories", []))
    return {**data, "stored_memories": saved, "meta": result["usage"]}


# ── Core ──────────────────────────────────────────────────────────────────────

@app.post(
    "/ai/context",
    tags=["Core"],
    summary="Generate context snapshot",
    description=(
        "Summarises the user's emotional + situational context. "
        "Used internally to feed other endpoints. Mood and energy can be auto-detected from `message`."
    ),
    response_model=ContextResponse,
)
async def ai_context(req: ContextRequest):
    user_prompt = _build_user_prompt(req, [
        f"Current mood: {_maybe(req.mood)}",
        f"Current energy: {_maybe(req.energy)}",
        f"Goals: {', '.join(req.goals) or 'none stated'}",
        "",
        "Generate the context snapshot.",
    ])
    return await _run_endpoint("context", req, user_prompt)


@app.post(
    "/ai/coach",
    tags=["Core"],
    summary="Generate a coach card",
    description=(
        "The primary coaching endpoint. Returns one motivational coach card personalised to the "
        "user's current mood, energy, and goals. Mood, energy, and personality can all be "
        "auto-detected from `message`."
    ),
    response_model=CoachResponse,
)
async def ai_coach(req: CoachRequest):
    user_prompt = _build_user_prompt(req, [
        f"Mood: {_maybe(req.mood)}",
        f"Energy: {_maybe(req.energy)}",
        f"Goals: {', '.join(req.goals) or 'none stated'}",
        "",
        "Generate one coach card now.",
    ])
    return await _run_endpoint("coach", req, user_prompt)


# ── Planning ──────────────────────────────────────────────────────────────────

@app.post(
    "/ai/focus",
    tags=["Planning"],
    summary="Generate today's focus tasks",
    description=(
        "Returns 1–3 small tasks that fit within the user's available free time and energy level. "
        "Energy can be auto-detected from `message`."
    ),
    response_model=FocusResponse,
)
async def ai_focus(req: FocusRequest):
    user_prompt = _build_user_prompt(req, [
        f"Goals: {', '.join(req.goals)}",
        f"Free minutes available: {req.free_minutes}",
        f"Energy: {_maybe(req.energy)}",
        "",
        "Generate today's focus tasks.",
    ])
    return await _run_endpoint("focus", req, user_prompt)


@app.post(
    "/ai/plan",
    tags=["Planning"],
    summary="Generate a day plan",
    description=(
        "Creates a personalised 2–4 item day plan based on goals, calendar gaps, mood, and energy. "
        "Mood and energy can be auto-detected from `message`."
    ),
    response_model=PlanResponse,
)
async def ai_plan(req: PlanRequest):
    user_prompt = _build_user_prompt(req, [
        f"Goals: {', '.join(req.goals)}",
        f"Calendar gaps: {', '.join(req.calendar_gaps) or 'none provided'}",
        f"Energy: {_maybe(req.energy)}",
        f"Mood: {_maybe(req.mood)}",
        "",
        "Generate a short day plan.",
    ])
    return await _run_endpoint("plan", req, user_prompt)


# ── Wellbeing ─────────────────────────────────────────────────────────────────

@app.post(
    "/ai/intervention",
    tags=["Wellbeing"],
    summary="Generate a distraction intervention",
    description=(
        "Playfully interrupts the user when they've been doom-scrolling, binge-watching, or "
        "procrastinating. Never judgmental — always kind and funny."
    ),
    response_model=InterventionResponse,
)
async def ai_intervention(req: InterventionRequest):
    user_prompt = _build_user_prompt(req, [
        f'User has been doing "{req.activity}" for {req.minutes_spent} minutes.',
        "",
        "Generate a playful, kind intervention card with one tiny alternative action.",
    ])
    return await _run_endpoint("intervention", req, user_prompt)


@app.post(
    "/ai/future-me",
    tags=["Wellbeing"],
    summary="Generate a Future Me projection",
    description=(
        "Projects a warm, realistic vision of the user's future if they maintain their current "
        "consistency on a given goal."
    ),
    response_model=FutureMeResponse,
)
async def ai_future_me(req: FutureMeRequest):
    user_prompt = _build_user_prompt(req, [
        f"Goal: {req.goal}",
        f"Current consistency: {req.consistency}%",
        "",
        'Generate a "Future You" projection card.',
    ])
    return await _run_endpoint("future-me", req, user_prompt)


@app.post(
    "/ai/recap",
    tags=["Wellbeing"],
    summary="Generate an evening recap",
    description=(
        "Summarises the user's day from their completed actions into a warm, proud-feeling recap card."
    ),
    response_model=RecapResponse,
)
async def ai_recap(req: RecapRequest):
    user_prompt = _build_user_prompt(req, [
        f"Completed today: {', '.join(req.completed_actions)}",
        f"Total points earned: {req.total_points}",
        "",
        "Generate the evening recap card.",
    ])
    return await _run_endpoint("recap", req, user_prompt)


# ── Engagement ────────────────────────────────────────────────────────────────

@app.post(
    "/ai/music",
    tags=["Engagement"],
    summary="Generate a music mood suggestion",
    description=(
        "Recommends a playlist vibe and genre tags based on the user's activity, mood, and energy. "
        "Never invents real artist names — describes genre and mood only. "
        "Mood and energy can be auto-detected from `message`."
    ),
    response_model=MusicResponse,
)
async def ai_music(req: MusicRequest):
    user_prompt = _build_user_prompt(req, [
        f"Activity: {req.activity}",
        f"Mood: {_maybe(req.mood)}",
        f"Energy: {_maybe(req.energy)}",
        "",
        "Generate a playlist mood suggestion.",
    ])
    return await _run_endpoint("music", req, user_prompt)


@app.post(
    "/ai/reward",
    tags=["Engagement"],
    summary="Generate a reward progress update",
    description=(
        "Encourages the user on their progress toward a self-chosen reward. "
        "Uses current points vs reward cost to motivate, never guilt."
    ),
    response_model=RewardResponse,
)
async def ai_reward(req: RewardRequest):
    user_prompt = _build_user_prompt(req, [
        f"Chosen reward: {req.reward}",
        f"Current points: {req.current_points}",
        f"Reward cost: {req.reward_cost}",
        "",
        "Generate a progress-toward-reward update.",
    ])
    return await _run_endpoint("reward", req, user_prompt)


@app.post(
    "/ai/goals/progress",
    tags=["Engagement"],
    summary="Generate a goal progress update",
    description=(
        "Returns an encouraging progress update with a realistic pace-based prediction "
        "for the given goal."
    ),
    response_model=GoalsProgressResponse,
)
async def ai_goals_progress(req: GoalsProgressRequest):
    user_prompt = _build_user_prompt(req, [
        f"Goal: {req.goal}",
        f"Current progress: {req.progress}%",
        f"Pace note: {req.pace_note or 'none provided'}",
        "",
        "Generate a progress update with a realistic prediction.",
    ])
    return await _run_endpoint("goals/progress", req, user_prompt)


# ── Master chat ───────────────────────────────────────────────────────────────

@app.post(
    "/ai/chat",
    tags=["Core"],
    summary="Master unified endpoint",
    description=(
        "Single entry point that replaces calling multiple endpoints separately. "
        "Pass everything you know about the user — the AI decides which cards to generate "
        "and returns them all in one response.\n\n"
        "**Cards returned based on what you provide:**\n"
        "- `coach` — always returned\n"
        "- `focus` — when `free_minutes` is set\n"
        "- `plan` — when `calendar_gaps` is set\n"
        "- `intervention` — when `current_activity` + `minutes_on_activity` are set\n"
        "- `recap` — when `completed_today` has items\n"
        "- `reward` — when `active_reward` is set\n"
        "- `music` — always returned (mood/energy aware)\n\n"
        "All detection (`mood`, `energy`, `coach_personality`) is auto-inferred from `message` when not explicitly set."
    ),
    response_model=ChatResponse,
)
async def ai_chat(req: ChatRequest):
    config = ENDPOINT_PROMPTS["chat"]

    memories = req.memories if req.memories is not None else get_memories(req.user_id)

    # Determine which cards to generate based on provided context
    cards = ["coach", "music"]
    if req.free_minutes:
        cards.append("focus")
    if req.calendar_gaps:
        cards.append("plan")
    if req.current_activity and req.minutes_on_activity:
        cards.append("intervention")
    if req.completed_today:
        cards.append("recap")
    if req.active_reward:
        cards.append("reward")

    # Build user prompt
    lines = [f'User message: "{req.message}"', ""]

    if req.goals:
        lines.append(f"Goals: {', '.join(req.goals)}")
    if req.mood:
        lines.append(f"Mood (explicit): {req.mood}")
    if req.energy:
        lines.append(f"Energy (explicit): {req.energy}")
    if req.free_minutes:
        lines.append(f"Free time available: {req.free_minutes} minutes")
    if req.calendar_gaps:
        lines.append(f"Calendar gaps: {', '.join(req.calendar_gaps)}")
    if req.completed_today:
        lines.append(f"Completed today: {', '.join(req.completed_today)}")
        lines.append(f"Points earned today: {req.total_points_today}")
    if req.active_reward:
        r = req.active_reward
        lines.append(
            f"Working toward reward: '{r.reward}' "
            f"({r.current_points}/{r.reward_cost} points)"
        )
    if req.current_activity and req.minutes_on_activity:
        lines.append(
            f"Currently doing: '{req.current_activity}' "
            f"for {req.minutes_on_activity} minutes"
        )

    lines += ["", f"CARDS TO GENERATE: {', '.join(cards)}", "Set all other cards to null."]
    user_prompt = "\n".join(lines)

    system_prompt = build_system_prompt(
        personality=req.coach_personality,
        memories=memories,
        extra_instructions=(
            f"{config['instructions']}\n\n"
            f"Return JSON matching EXACTLY this schema:\n{config['schema']}"
        ),
        needs_mood_detection=req.mood is None,
        needs_energy_detection=req.energy is None,
    )

    try:
        result = await call_claude_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=1500,
        )
    except AIServiceError as err:
        raise HTTPException(
            status_code=err.status_code,
            detail={"error": err.code, "message": err.message},
        )

    return {**result["data"], "meta": result["usage"]}


# ── Streaming (SSE) ───────────────────────────────────────────────────────────

@app.post(
    "/ai/coach/stream",
    tags=["Core"],
    summary="Coach card — streaming (SSE)",
    description=(
        "Same as `/ai/coach` but streams the response as Server-Sent Events. "
        "Each `data:` event is a text delta. An `event: done` marks completion."
    ),
)
async def ai_coach_stream(req: CoachRequest):
    config    = ENDPOINT_PROMPTS["coach"]
    memories  = _resolve_memories(req)
    mood      = getattr(req, "mood", None)
    energy    = getattr(req, "energy", None)

    system_prompt = build_system_prompt(
        personality=req.coach_personality,
        memories=memories,
        extra_instructions=(
            f"{config['instructions']}\n\n"
            f"Return JSON matching EXACTLY this schema:\n{config['schema']}"
        ),
        needs_mood_detection=mood is None,
        needs_energy_detection=energy is None,
    )
    user_prompt = _build_user_prompt(req, [
        f"Mood: {_maybe(req.mood)}",
        f"Energy: {_maybe(req.energy)}",
        f"Goals: {', '.join(req.goals) or 'none stated'}",
        "",
        "Generate one coach card now.",
    ])

    async def event_stream():
        try:
            async for delta in stream_claude(system_prompt=system_prompt, user_prompt=user_prompt, max_tokens=450):
                yield f"data: {delta}\n\n"
            yield "event: done\ndata: {}\n\n"
        except AIServiceError as err:
            yield f'event: error\ndata: {{"error": "{err.code}", "message": "{err.message}"}}\n\n'

    return StreamingResponse(event_stream(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
