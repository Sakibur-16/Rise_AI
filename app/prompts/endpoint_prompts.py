"""
Per-endpoint instructions + JSON schema contracts.

Every schema includes:
  - `detected_personality` — which personality was used (explicit or auto-chosen)
  - `detected_mood`        — on mood-aware endpoints, the mood used (provided or inferred)

These fields let the frontend cache what the AI actually used for each call.
"""

ENDPOINT_PROMPTS = {
    # ── Core ──────────────────────────────────────────────────────────────────
    "context": {
        "instructions": (
            "Summarise the user's current emotional + situational context in one short internal snapshot. "
            "This powers other endpoints, so be accurate rather than motivational here (still max 80 words)."
        ),
        "schema": """{
  "mood": string,
  "energy": "low" | "medium" | "high",
  "summary": string,
  "suggested_focus_area": string,
  "detected_mood": string,
  "detected_personality": string
}""",
    },

    "coach": {
        "instructions": (
            "Generate ONE coach card responding to the user's current mood, energy, and goals. "
            "Follow the emotional arc exactly: acknowledge → tiny action → why → reward. "
            "actions: 1–3 micro-tasks, each under 15 words. points: 10–100 based on effort."
        ),
        "schema": """{
  "message": string,
  "actions": [string],
  "points": number,
  "emotion": string,
  "detected_mood": string,
  "detected_personality": string
}""",
    },

    # ── Planning ───────────────────────────────────────────────────────────────
    "focus": {
        "instructions": (
            "Generate 1–3 small focus tasks that fit within the user's available free_minutes and energy level. "
            "Every task must be realistically completable in the given time window. "
            "points per task: 10–50, higher for harder tasks."
        ),
        "schema": """{
  "focus_title": string,
  "focus_message": string,
  "tasks": [
    { "title": string, "points": number }
  ],
  "detected_personality": string
}""",
    },

    "plan": {
        "instructions": (
            "Create a short personalised day plan based on goals, calendar gaps, energy, and mood. "
            "2–4 items max — suggest don't overload. time_suggestion is a human label like '9am' or 'after lunch'. "
            "points per item: 10–75."
        ),
        "schema": """{
  "plan_title": string,
  "plan_message": string,
  "items": [
    { "title": string, "time_suggestion": string, "points": number }
  ],
  "detected_mood": string,
  "detected_personality": string
}""",
    },

    # ── Wellbeing ──────────────────────────────────────────────────────────────
    "intervention": {
        "instructions": (
            "The user is doom-scrolling, binge-watching, or wasting time. Interrupt playfully and kindly — "
            "never judgmental. Offer ONE fun, tiny alternative action. Light humour where personality allows. "
            "cta: short button label like 'Do it' or 'Let's go'."
        ),
        "schema": """{
  "title": string,
  "message": string,
  "points": number,
  "cta": string,
  "detected_personality": string
}""",
    },

    "future-me": {
        "instructions": (
            "Project a warm, realistic, emotionally compelling vision of the user's future if they stay "
            "consistent with their goal at the given consistency %. Be specific but never overpromise."
        ),
        "schema": """{
  "title": string,
  "message": string,
  "detected_personality": string
}""",
    },

    "recap": {
        "instructions": (
            "Summarise the user's day from their completed actions into a warm evening recap. "
            "Make them feel proud. End with a brief forward-looking note (warmth, not a new task). "
            "completed: echo back the completed_actions list as-is."
        ),
        "schema": """{
  "title": string,
  "message": string,
  "completed": [string],
  "total_points": number,
  "detected_personality": string
}""",
    },

    # ── Engagement ────────────────────────────────────────────────────────────
    "music": {
        "instructions": (
            "Suggest a music mood/playlist vibe based on the user's activity, mood, and energy. "
            "Do NOT invent real artist names or song titles — describe genre and vibe only. "
            "genre_tags: 2–5 short tags like ['lo-fi', 'chill', 'instrumental']."
        ),
        "schema": """{
  "playlist_mood": string,
  "message": string,
  "genre_tags": [string],
  "detected_mood": string,
  "detected_personality": string
}""",
    },

    "reward": {
        "instructions": (
            "Give the user an encouraging progress update toward their self-chosen reward. "
            "points_remaining = reward_cost - current_points (never negative). "
            "Motivate without guilt — celebrate how far they've come."
        ),
        "schema": """{
  "reward": string,
  "points_remaining": number,
  "message": string,
  "detected_personality": string
}""",
    },

    "goals/progress": {
        "instructions": (
            "Given a goal and current progress %, generate an encouraging update with a realistic projection. "
            "prediction must extrapolate from current pace — don't guess wildly. "
            "Example: 'At this pace you'll hit 100% in ~3 weeks.'"
        ),
        "schema": """{
  "goal": string,
  "progress": number,
  "message": string,
  "prediction": string,
  "detected_personality": string
}""",
    },

    # ── Memory ────────────────────────────────────────────────────────────────
    "memory/extract": {
        "instructions": (
            "Extract durable personalisation facts from the user's raw input. "
            "Only extract facts likely to stay true for weeks/months (preferences, patterns, routines, tendencies). "
            "Do NOT extract one-off states ('I'm tired today'). "
            "confidence: how certain you are these are genuine durable facts."
        ),
        "schema": """{
  "memories": [string],
  "confidence": "low" | "medium" | "high"
}""",
    },
}
