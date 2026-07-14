"""
Request & response models for every /ai/* endpoint.

Field rules:
- `message`          — raw user text; drives mood + personality auto-detection
- `coach_personality`— use "auto" to let the AI pick from the tone of `message`
- `mood`             — explicit or leave None → auto-inferred from `message`
- `energy`           — explicit or leave None → auto-inferred from `message`
"""

from typing import Optional, Literal
from pydantic import BaseModel, Field, ConfigDict

# ── Shared types ──────────────────────────────────────────────────────────────

CoachPersonality = Literal["auto", "sweet", "strict", "sarcastic", "ceo", "therapeutic"]
EnergyLevel      = Literal["low", "medium", "high"]

_PERSONALITY_DESC = (
    "Tone of the AI response.\n\n"
    "| Value | Style |\n"
    "|---|---|\n"
    "| `auto` | AI picks based on your `message` tone |\n"
    "| `sweet` | Warm, nurturing best-friend energy |\n"
    "| `strict` | Direct, no-nonsense coach |\n"
    "| `sarcastic` | Witty, teasing but genuinely caring |\n"
    "| `ceo` | Strategic, results-driven operator |\n"
    "| `therapeutic` | Calm, validating, trauma-informed |"
)

_MESSAGE_DESC = (
    "Raw user message or chat input. When provided the AI uses it to:\n"
    "- Infer **mood** if `mood` is not set\n"
    "- Infer **energy** if `energy` is not set\n"
    "- Choose the best **personality** when `coach_personality` is `auto`"
)


# ── Base request ──────────────────────────────────────────────────────────────

class BaseAIRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {
        "user_id": "user_001",
        "message": "I'm exhausted and can't bring myself to do anything today",
        "coach_personality": "auto",
        "memories": ["Wants to lose 5kg before summer", "Prefers morning workouts"],
    }})

    user_id: Optional[str] = Field(
        None,
        description="User ID. When set, stored memories are auto-loaded for this user.",
        examples=["user_001"],
    )
    message: Optional[str] = Field(
        None,
        description=_MESSAGE_DESC,
        examples=["I'm exhausted and nothing feels doable today"],
    )
    memories: Optional[list[str]] = Field(
        None,
        description="Inline memories for this request. Overrides stored memories when provided.",
        examples=[["Wants to lose 5kg before summer", "Prefers morning workouts"]],
    )
    coach_personality: CoachPersonality = Field(
        "auto",
        description=_PERSONALITY_DESC,
        examples=["auto"],
    )


# ── Request models ────────────────────────────────────────────────────────────

class ContextRequest(BaseAIRequest):
    model_config = ConfigDict(json_schema_extra={"example": {
        "user_id": "user_001",
        "message": "I woke up feeling anxious with a big presentation today",
        "coach_personality": "auto",
        "mood": "anxious",
        "energy": "low",
        "goals": ["Nail the presentation", "Drink 2L of water"],
    }})

    mood: Optional[str] = Field(
        None,
        description="Current mood. Leave blank to auto-detect from `message`.",
        examples=["anxious", "tired", "motivated"],
    )
    energy: Optional[EnergyLevel] = Field(
        None,
        description="Current energy level. Leave blank to auto-detect from `message`.",
        examples=["low"],
    )
    goals: list[str] = Field(
        [],
        description="Active goals for context.",
        examples=[["Nail the presentation", "Drink 2L of water"]],
    )


class CoachRequest(BaseAIRequest):
    model_config = ConfigDict(json_schema_extra={"example": {
        "user_id": "user_001",
        "message": "I'm really tired and can't bring myself to work out",
        "coach_personality": "auto",
        "mood": "tired",
        "energy": "low",
        "goals": ["Exercise 3x this week", "Drink 2L of water daily", "Sleep before midnight"],
    }})

    mood: Optional[str] = Field(
        None,
        description="Current mood. Leave blank to auto-detect from `message`.",
        examples=["tired", "anxious", "motivated"],
    )
    energy: Optional[EnergyLevel] = Field(
        None,
        description="Current energy level. Leave blank to auto-detect from `message`.",
        examples=["low"],
    )
    goals: list[str] = Field(
        [],
        description="Active goals for personalized suggestions.",
        examples=[["Exercise 3x this week", "Sleep before midnight"]],
    )


class FocusRequest(BaseAIRequest):
    model_config = ConfigDict(json_schema_extra={"example": {
        "user_id": "user_001",
        "message": "I have a spare hour, help me use it well",
        "coach_personality": "ceo",
        "goals": ["Finish project report", "Exercise 3x this week"],
        "free_minutes": 60,
        "energy": "medium",
    }})

    goals: list[str] = Field(
        ...,
        description="Active goals to build focus tasks from.",
        examples=[["Finish project report", "Exercise 3x this week"]],
    )
    free_minutes: int = Field(
        ...,
        ge=5,
        le=480,
        description="Available free time in minutes (5–480).",
        examples=[60],
    )
    energy: Optional[EnergyLevel] = Field(
        None,
        description="Current energy level. Affects task intensity. Auto-detected from `message` if blank.",
        examples=["medium"],
    )


class PlanRequest(BaseAIRequest):
    model_config = ConfigDict(json_schema_extra={"example": {
        "user_id": "user_001",
        "message": "Help me plan my day, I feel focused today",
        "coach_personality": "auto",
        "goals": ["Finish project report", "Go for a run"],
        "calendar_gaps": ["9am-11am", "3pm-5pm"],
        "energy": "medium",
        "mood": "focused",
    }})

    goals: list[str] = Field(
        ...,
        description="Goals to plan around.",
        examples=[["Finish project report", "Go for a run"]],
    )
    calendar_gaps: list[str] = Field(
        [],
        description="Available time blocks (e.g. '9am–11am').",
        examples=[["9am-11am", "3pm-5pm"]],
    )
    energy: Optional[EnergyLevel] = Field(
        None,
        description="Current energy level. Auto-detected from `message` if blank.",
        examples=["medium"],
    )
    mood: Optional[str] = Field(
        None,
        description="Current mood. Auto-detected from `message` if blank.",
        examples=["focused", "neutral"],
    )


class InterventionRequest(BaseAIRequest):
    model_config = ConfigDict(json_schema_extra={"example": {
        "user_id": "user_001",
        "coach_personality": "sarcastic",
        "activity": "doom-scrolling Instagram",
        "minutes_spent": 47,
    }})

    activity: str = Field(
        ...,
        description="The distraction activity the user has been doing.",
        examples=["doom-scrolling Instagram", "binge-watching Netflix"],
    )
    minutes_spent: int = Field(
        ...,
        ge=1,
        description="Minutes spent on the distraction.",
        examples=[47],
    )


class FutureMeRequest(BaseAIRequest):
    model_config = ConfigDict(json_schema_extra={"example": {
        "user_id": "user_001",
        "coach_personality": "therapeutic",
        "goal": "Lose 5kg before summer",
        "consistency": 72,
    }})

    goal: str = Field(
        ...,
        description="The goal to project into the user's future.",
        examples=["Lose 5kg before summer", "Read 24 books this year"],
    )
    consistency: int = Field(
        ...,
        ge=0,
        le=100,
        description="How consistently the user has worked on this goal (0–100%).",
        examples=[72],
    )


class RecapRequest(BaseAIRequest):
    model_config = ConfigDict(json_schema_extra={"example": {
        "user_id": "user_001",
        "coach_personality": "sweet",
        "completed_actions": ["Went for a 20-min walk", "Drank 2L of water", "Read 10 pages"],
        "total_points": 150,
    }})

    completed_actions: list[str] = Field(
        ...,
        description="Things the user completed today.",
        examples=[["Went for a 20-min walk", "Drank 2L of water", "Read 10 pages"]],
    )
    total_points: int = Field(
        0,
        ge=0,
        description="Total points earned today.",
        examples=[150],
    )


class MusicRequest(BaseAIRequest):
    model_config = ConfigDict(json_schema_extra={"example": {
        "user_id": "user_001",
        "message": "About to sit down for a deep work session",
        "coach_personality": "ceo",
        "activity": "deep work session",
        "mood": "focused",
        "energy": "high",
    }})

    activity: str = Field(
        ...,
        description="What the user is about to do.",
        examples=["deep work session", "morning run", "winding down before bed"],
    )
    mood: Optional[str] = Field(
        None,
        description="Current mood. Auto-detected from `message` if blank.",
        examples=["focused", "calm"],
    )
    energy: Optional[EnergyLevel] = Field(
        None,
        description="Current energy level. Auto-detected from `message` if blank.",
        examples=["high"],
    )


class RewardRequest(BaseAIRequest):
    model_config = ConfigDict(json_schema_extra={"example": {
        "user_id": "user_001",
        "coach_personality": "sweet",
        "reward": "New running shoes",
        "current_points": 340,
        "reward_cost": 500,
    }})

    reward: str = Field(
        ...,
        description="The reward the user is working toward.",
        examples=["New running shoes", "Weekend spa day"],
    )
    current_points: int = Field(
        ...,
        ge=0,
        description="User's current point balance.",
        examples=[340],
    )
    reward_cost: int = Field(
        ...,
        ge=1,
        description="Point cost of the reward.",
        examples=[500],
    )


class GoalsProgressRequest(BaseAIRequest):
    model_config = ConfigDict(json_schema_extra={"example": {
        "user_id": "user_001",
        "coach_personality": "ceo",
        "goal": "Read 24 books this year",
        "progress": 58,
        "pace_note": "Finished 2 books last month",
    }})

    goal: str = Field(
        ...,
        description="The goal to report progress on.",
        examples=["Read 24 books this year", "Exercise 3x per week"],
    )
    progress: int = Field(
        ...,
        ge=0,
        le=100,
        description="Current progress percentage (0–100).",
        examples=[58],
    )
    pace_note: str = Field(
        "",
        description="Optional note about recent pace or context.",
        examples=["Finished 2 books last month", "Skipped last week due to travel"],
    )


class ActiveReward(BaseModel):
    reward:         str
    current_points: int = Field(..., ge=0)
    reward_cost:    int = Field(..., ge=1)


class ChatRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {
        "user_id": "user_001",
        "message": "I'm exhausted but I have some free time this afternoon",
        "coach_personality": "auto",
        "goals": ["Exercise 3x this week", "Read 24 books this year"],
        "mood": None,
        "energy": None,
        "free_minutes": 45,
        "calendar_gaps": ["3pm-5pm"],
        "completed_today": ["Morning walk 20 min", "Read 15 pages"],
        "total_points_today": 120,
        "active_reward": {
            "reward": "New running shoes",
            "current_points": 340,
            "reward_cost": 500,
        },
        "current_activity": "doom-scrolling Instagram",
        "minutes_on_activity": 35,
    }})

    user_id:              str = Field(..., description="User ID. Stored memories are auto-loaded.", examples=["user_001"])
    message:              str = Field(..., description=_MESSAGE_DESC, examples=["I'm exhausted but have some free time"])
    coach_personality:    CoachPersonality = Field("auto", description=_PERSONALITY_DESC)
    memories:             Optional[list[str]] = Field(None, description="Inline memories. Overrides stored memories when provided.")

    goals:                list[str] = Field([], description="Active goals.", examples=[["Exercise 3x this week"]])
    mood:                 Optional[str] = Field(None, description="Current mood. Auto-detected from `message` if null.")
    energy:               Optional[EnergyLevel] = Field(None, description="Current energy. Auto-detected from `message` if null.")

    free_minutes:         Optional[int] = Field(None, ge=5, le=480, description="Free time available (minutes). Triggers a **focus** card.")
    calendar_gaps:        list[str] = Field([], description="Free time blocks e.g. '9am–11am'. Triggers a **plan** card.", examples=[["3pm-5pm"]])

    completed_today:      list[str] = Field([], description="Actions completed today. Triggers a **recap** card.", examples=[["Morning walk", "Read 15 pages"]])
    total_points_today:   int = Field(0, ge=0, description="Points earned today. Used in recap.")

    active_reward:        Optional[ActiveReward] = Field(None, description="Reward the user is working toward. Triggers a **reward** card.")

    current_activity:     Optional[str] = Field(None, description="Distraction activity in progress. Triggers an **intervention** card.", examples=["doom-scrolling Instagram"])
    minutes_on_activity:  Optional[int] = Field(None, ge=1, description="Minutes spent on the distraction.", examples=[35])


class MemoryExtractRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {
        "user_id": "user_001",
        "text": "I usually work out in the mornings and I really struggle to sleep before midnight. I hate running but love swimming.",
    }})

    user_id: str = Field(
        ...,
        description="User ID to attach extracted memories to.",
        examples=["user_001"],
    )
    text: str = Field(
        ...,
        description="Raw message, chat history, or journal entry to extract memories from.",
        examples=["I usually work out in the mornings and really struggle to sleep before midnight."],
    )


# ── Response models ───────────────────────────────────────────────────────────

class UsageMeta(BaseModel):
    input_tokens:  int
    output_tokens: int
    cost_usd:      float


class ContextResponse(BaseModel):
    mood:                  str
    energy:                EnergyLevel
    summary:               str
    suggested_focus_area:  str
    detected_mood:         Optional[str] = None
    detected_personality:  Optional[str] = None
    meta:                  UsageMeta


class CoachResponse(BaseModel):
    message:              str
    actions:              list[str]
    points:               int
    emotion:              str
    detected_mood:        Optional[str] = None
    detected_personality: Optional[str] = None
    meta:                 UsageMeta


class FocusTask(BaseModel):
    title:  str
    points: int


class FocusResponse(BaseModel):
    focus_title:          str
    focus_message:        str
    tasks:                list[FocusTask]
    detected_personality: Optional[str] = None
    meta:                 UsageMeta


class PlanItem(BaseModel):
    title:           str
    time_suggestion: str
    points:          int


class PlanResponse(BaseModel):
    plan_title:           str
    plan_message:         str
    items:                list[PlanItem]
    detected_mood:        Optional[str] = None
    detected_personality: Optional[str] = None
    meta:                 UsageMeta


class InterventionResponse(BaseModel):
    title:                str
    message:              str
    points:               int
    cta:                  str
    detected_personality: Optional[str] = None
    meta:                 UsageMeta


class FutureMeResponse(BaseModel):
    title:                str
    message:              str
    detected_personality: Optional[str] = None
    meta:                 UsageMeta


class RecapResponse(BaseModel):
    title:                str
    message:              str
    completed:            list[str]
    total_points:         int
    detected_personality: Optional[str] = None
    meta:                 UsageMeta


class MusicResponse(BaseModel):
    playlist_mood:        str
    message:              str
    genre_tags:           list[str]
    detected_mood:        Optional[str] = None
    detected_personality: Optional[str] = None
    meta:                 UsageMeta


class RewardResponse(BaseModel):
    reward:               str
    points_remaining:     int
    message:              str
    detected_personality: Optional[str] = None
    meta:                 UsageMeta


class GoalsProgressResponse(BaseModel):
    goal:                 str
    progress:             int
    message:              str
    prediction:           str
    detected_personality: Optional[str] = None
    meta:                 UsageMeta


class MemoryExtractResponse(BaseModel):
    memories:        list[str]
    confidence:      Literal["low", "medium", "high"]
    stored_memories: list[str]
    meta:            UsageMeta


class HealthResponse(BaseModel):
    status:  str
    service: str


class CostResponse(BaseModel):
    total_input_tokens:  int
    total_output_tokens: int
    total_cost_usd:      float
    call_count:          int


class MemoryReadResponse(BaseModel):
    user_id:  str
    memories: list[str]


# ── Chat (master) card types ──────────────────────────────────────────────────

class CoachCard(BaseModel):
    message: str
    actions: list[str]
    points:  int
    emotion: str


class FocusCard(BaseModel):
    focus_title:   str
    focus_message: str
    tasks:         list[FocusTask]


class PlanCard(BaseModel):
    plan_title:   str
    plan_message: str
    items:        list[PlanItem]


class InterventionCard(BaseModel):
    title:   str
    message: str
    points:  int
    cta:     str


class MusicCard(BaseModel):
    playlist_mood: str
    message:       str
    genre_tags:    list[str]


class RewardCard(BaseModel):
    reward:           str
    points_remaining: int
    message:          str


class RecapCard(BaseModel):
    title:        str
    message:      str
    completed:    list[str]
    total_points: int


class ChatResponse(BaseModel):
    intent:               str
    detected_mood:        str
    detected_energy:      EnergyLevel
    detected_personality: str

    coach:        CoachCard
    focus:        Optional[FocusCard]        = None
    plan:         Optional[PlanCard]         = None
    intervention: Optional[InterventionCard] = None
    music:        Optional[MusicCard]        = None
    reward:       Optional[RewardCard]       = None
    recap:        Optional[RecapCard]        = None

    meta: UsageMeta
