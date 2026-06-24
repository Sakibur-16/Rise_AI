"""
Request models for every /ai/* endpoint.

This is the contract your backend dev needs: exact field names, types,
and which fields are required vs optional. FastAPI auto-validates against
these, and auto-generates the OpenAPI docs at /docs from them.
"""

from typing import Optional, Literal
from pydantic import BaseModel, Field

Personality = Literal["sweet", "strict", "sarcastic", "ceo", "therapeutic"]


class BaseAIRequest(BaseModel):
    user_id: Optional[str] = Field(None, description="If provided, stored memories for this user are auto-loaded.")
    memories: Optional[list[str]] = Field(
        None, description="Inline memories. If provided, takes priority over stored memories for user_id."
    )
    coach_personality: Optional[Personality] = Field("sweet", description="Tone of voice for the response.")


class ContextRequest(BaseAIRequest):
    mood: str
    energy: Literal["low", "medium", "high"]
    goals: list[str] = []


class CoachRequest(BaseAIRequest):
    mood: str
    energy: Literal["low", "medium", "high"]
    goals: list[str] = []


class FocusRequest(BaseAIRequest):
    goals: list[str]
    free_minutes: int
    energy: Literal["low", "medium", "high"] = "medium"


class PlanRequest(BaseAIRequest):
    goals: list[str]
    calendar_gaps: list[str] = []
    energy: Literal["low", "medium", "high"] = "medium"
    mood: str = "neutral"


class InterventionRequest(BaseAIRequest):
    activity: str
    minutes_spent: int


class FutureMeRequest(BaseAIRequest):
    goal: str
    consistency: int = Field(..., ge=0, le=100, description="Consistency percentage, 0-100.")


class RecapRequest(BaseAIRequest):
    completed_actions: list[str]
    total_points: int = 0


class MusicRequest(BaseAIRequest):
    activity: str
    mood: str
    energy: Literal["low", "medium", "high"] = "medium"


class RewardRequest(BaseAIRequest):
    reward: str
    current_points: int
    reward_cost: int


class GoalsProgressRequest(BaseAIRequest):
    goal: str
    progress: int = Field(..., ge=0, le=100)
    pace_note: str = ""


class MemoryExtractRequest(BaseModel):
    user_id: str
    text: str
