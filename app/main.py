"""
Rise AI Microservice — FastAPI entrypoint.

This is the entire AI layer. Your backend (Node/Express, or whatever you use)
calls these endpoints over HTTP and gets card-ready JSON back. Nothing here
does auth, payments, persistence, or business logic outside the AI itself —
that's all your backend's job.

Run locally:
    uvicorn app.main:app --reload --port 8000
  OR:
    python app/main.py

Interactive API docs (auto-generated from the Pydantic models in models.py):
    http://localhost:8000/docs
"""

import sys
import os

# Ensure the project root is on sys.path so "app.*" imports work whether this
# file is launched via `uvicorn app.main:app` or `python app/main.py`.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv

load_dotenv()

from app.models import (
    ContextRequest,
    CoachRequest,
    FocusRequest,
    PlanRequest,
    InterventionRequest,
    FutureMeRequest,
    RecapRequest,
    MusicRequest,
    RewardRequest,
    GoalsProgressRequest,
    MemoryExtractRequest,
)
from app.prompts.base_prompt import build_system_prompt
from app.prompts.endpoint_prompts import ENDPOINT_PROMPTS
from app.services.claude_client import call_claude_json, stream_claude, get_cost_ledger, AIServiceError
from app.services.memory_store import get_memories, add_memories

app = FastAPI(
    title="Rise AI Microservice",
    description="AI-only backend for the Rise app: coach, focus, intervention, future-me, and related endpoints.",
    version="1.0.0",
)


def _resolve_memories(req: "BaseAIRequest") -> list[str]:
    if req.memories:
        return req.memories
    return get_memories(req.user_id)


async def _run_endpoint(endpoint_key: str, req, user_prompt: str) -> dict:
    """Shared logic: build prompt -> call Claude -> return JSON. Used by every endpoint below."""
    config = ENDPOINT_PROMPTS[endpoint_key]
    memories = _resolve_memories(req)

    system_prompt = build_system_prompt(
        personality=req.coach_personality,
        memories=memories,
        extra_instructions=(
            f"{config['instructions']}\n\n"
            f"Return JSON matching EXACTLY this schema (no extra fields):\n{config['schema']}"
        ),
    )

    try:
        result = await call_claude_json(system_prompt=system_prompt, user_prompt=user_prompt, max_tokens=400)
    except AIServiceError as err:
        raise HTTPException(status_code=err.status_code, detail={"error": err.code, "message": err.message})

    return {**result["data"], "_meta": {"usage": result["usage"]}}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "rise-ai-microservice"}


@app.get("/ai/cost")
async def cost():
    """Running token + cost totals since the process started. Dev visibility only — resets on restart."""
    return get_cost_ledger()


@app.get("/ai/memory/{user_id}")
async def read_memory(user_id: str):
    """Convenience read endpoint so the memory engine is actually inspectable without a DB."""
    return {"user_id": user_id, "memories": get_memories(user_id)}


# ---------------------------------------------------------------------------
# POST /ai/context
# ---------------------------------------------------------------------------
@app.post("/ai/context")
async def ai_context(req: ContextRequest):
    user_prompt = (
        f"Current mood: {req.mood}\nCurrent energy: {req.energy}\n"
        f"Goals: {', '.join(req.goals) or 'none stated'}\n\nGenerate the context snapshot."
    )
    return await _run_endpoint("context", req, user_prompt)


# ---------------------------------------------------------------------------
# POST /ai/coach
# ---------------------------------------------------------------------------
@app.post("/ai/coach")
async def ai_coach(req: CoachRequest):
    user_prompt = (
        f"Mood: {req.mood}\nEnergy: {req.energy}\n"
        f"Goals: {', '.join(req.goals) or 'none stated'}\n\nGenerate one coach card now."
    )
    return await _run_endpoint("coach", req, user_prompt)


# ---------------------------------------------------------------------------
# POST /ai/focus
# ---------------------------------------------------------------------------
@app.post("/ai/focus")
async def ai_focus(req: FocusRequest):
    user_prompt = (
        f"Goals: {', '.join(req.goals)}\nFree minutes available today: {req.free_minutes}\n"
        f"Energy: {req.energy}\n\nGenerate today's focus."
    )
    return await _run_endpoint("focus", req, user_prompt)


# ---------------------------------------------------------------------------
# POST /ai/plan
# ---------------------------------------------------------------------------
@app.post("/ai/plan")
async def ai_plan(req: PlanRequest):
    user_prompt = (
        f"Goals: {', '.join(req.goals)}\nAvailable calendar gaps: {', '.join(req.calendar_gaps) or 'none provided'}\n"
        f"Energy: {req.energy}\nMood: {req.mood}\n\nGenerate a short plan."
    )
    return await _run_endpoint("plan", req, user_prompt)


# ---------------------------------------------------------------------------
# POST /ai/intervention
# ---------------------------------------------------------------------------
@app.post("/ai/intervention")
async def ai_intervention(req: InterventionRequest):
    user_prompt = (
        f'User has been doing "{req.activity}" for {req.minutes_spent} minutes.\n\n'
        "Generate a playful, kind intervention card with one tiny alternative action."
    )
    return await _run_endpoint("intervention", req, user_prompt)


# ---------------------------------------------------------------------------
# POST /ai/future-me
# ---------------------------------------------------------------------------
@app.post("/ai/future-me")
async def ai_future_me(req: FutureMeRequest):
    user_prompt = (
        f"Goal: {req.goal}\nCurrent consistency: {req.consistency}%\n\nGenerate a \"Future You\" projection card."
    )
    return await _run_endpoint("future-me", req, user_prompt)


# ---------------------------------------------------------------------------
# POST /ai/recap
# ---------------------------------------------------------------------------
@app.post("/ai/recap")
async def ai_recap(req: RecapRequest):
    user_prompt = (
        f"Completed today: {', '.join(req.completed_actions)}\nTotal points earned: {req.total_points}\n\n"
        "Generate the evening recap card."
    )
    return await _run_endpoint("recap", req, user_prompt)


# ---------------------------------------------------------------------------
# POST /ai/music
# ---------------------------------------------------------------------------
@app.post("/ai/music")
async def ai_music(req: MusicRequest):
    user_prompt = (
        f"Activity: {req.activity}\nMood: {req.mood}\nEnergy: {req.energy}\n\n"
        "Generate a playlist mood suggestion."
    )
    return await _run_endpoint("music", req, user_prompt)


# ---------------------------------------------------------------------------
# POST /ai/reward
# ---------------------------------------------------------------------------
@app.post("/ai/reward")
async def ai_reward(req: RewardRequest):
    user_prompt = (
        f"Chosen reward: {req.reward}\nCurrent points: {req.current_points}\nReward cost: {req.reward_cost}\n\n"
        "Generate a progress-toward-reward update."
    )
    return await _run_endpoint("reward", req, user_prompt)


# ---------------------------------------------------------------------------
# POST /ai/goals/progress
# ---------------------------------------------------------------------------
@app.post("/ai/goals/progress")
async def ai_goals_progress(req: GoalsProgressRequest):
    user_prompt = (
        f"Goal: {req.goal}\nCurrent progress: {req.progress}%\nPace note: {req.pace_note or 'none provided'}\n\n"
        "Generate a progress update with a realistic prediction."
    )
    return await _run_endpoint("goals/progress", req, user_prompt)


# ---------------------------------------------------------------------------
# POST /ai/memory/extract
# This one both calls Claude AND writes results into the memory store,
# so it doesn't go through the shared _run_endpoint helper.
# ---------------------------------------------------------------------------
@app.post("/ai/memory/extract")
async def ai_memory_extract(req: MemoryExtractRequest):
    config = ENDPOINT_PROMPTS["memory/extract"]
    system_prompt = build_system_prompt(
        extra_instructions=(
            f"{config['instructions']}\n\n"
            f"Return JSON matching EXACTLY this schema (no extra fields):\n{config['schema']}"
        ),
    )
    user_prompt = f'Raw input from user:\n"{req.text}"\n\nExtract durable memories, if any.'

    try:
        result = await call_claude_json(system_prompt=system_prompt, user_prompt=user_prompt, max_tokens=250)
    except AIServiceError as err:
        raise HTTPException(status_code=err.status_code, detail={"error": err.code, "message": err.message})

    data = result["data"]
    saved = add_memories(req.user_id, data.get("memories", []))

    return {**data, "stored_memories": saved, "_meta": {"usage": result["usage"]}}


# ---------------------------------------------------------------------------
# Streaming variants — one example wired up (coach); same pattern applies
# to any endpoint above if your backend dev wants SSE instead of single JSON.
# ---------------------------------------------------------------------------
@app.post("/ai/coach/stream")
async def ai_coach_stream(req: CoachRequest):
    config = ENDPOINT_PROMPTS["coach"]
    memories = _resolve_memories(req)
    system_prompt = build_system_prompt(
        personality=req.coach_personality,
        memories=memories,
        extra_instructions=(
            f"{config['instructions']}\n\n"
            f"Return JSON matching EXACTLY this schema (no extra fields):\n{config['schema']}"
        ),
    )
    user_prompt = (
        f"Mood: {req.mood}\nEnergy: {req.energy}\n"
        f"Goals: {', '.join(req.goals) or 'none stated'}\n\nGenerate one coach card now."
    )

    async def event_stream():
        try:
            async for delta in stream_claude(system_prompt=system_prompt, user_prompt=user_prompt, max_tokens=400):
                yield f"data: {delta}\n\n"
            yield "event: done\ndata: {}\n\n"
        except AIServiceError as err:
            yield f'event: error\ndata: {{"error": "{err.code}", "message": "{err.message}"}}\n\n'

    return StreamingResponse(event_stream(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
