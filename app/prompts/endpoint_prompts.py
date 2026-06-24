"""
Per-endpoint instructions + JSON schema contracts.

Schemas are kept strict and minimal — your backend dev renders these
directly into mobile cards, so field names here are the contract.
"""

ENDPOINT_PROMPTS = {
    "context": {
        "instructions": """Summarize the user's current emotional + situational context in one short internal snapshot.
This is used by other endpoints, not shown directly to the user, so it can be slightly more descriptive (still max 80 words).""",
        "schema": """{
  "mood": string,
  "energy": "low" | "medium" | "high",
  "summary": string,
  "suggested_focus_area": string
}""",
    },
    "coach": {
        "instructions": """Generate ONE coach card responding to the user's current mood/energy and goals.
Follow the emotional arc rule exactly: acknowledge -> tiny action -> why -> reward.""",
        "schema": """{
  "message": string,
  "actions": [string],
  "points": number,
  "emotion": string
}""",
    },
    "focus": {
        "instructions": """Generate today's focus: 1-3 small tasks that fit the user's available free_minutes and energy level.
Tasks must be realistically completable in the given time window.""",
        "schema": """{
  "focus_title": string,
  "focus_message": string,
  "tasks": [
    { "title": string, "points": number }
  ]
}""",
    },
    "plan": {
        "instructions": """Create a short personalized plan/schedule suggestion based on goals, calendar gaps, energy, and mood.
Do not overload the day — 2-4 items max. This is a suggestion, not a rigid schedule.""",
        "schema": """{
  "plan_title": string,
  "plan_message": string,
  "items": [
    { "title": string, "time_suggestion": string, "points": number }
  ]
}""",
    },
    "intervention": {
        "instructions": """The user is doom-scrolling, binge-watching, or wasting time. Interrupt playfully and kindly — never judgmental.
Offer ONE fun, tiny alternative action. Keep it light and funny if personality allows.""",
        "schema": """{
  "title": string,
  "message": string,
  "points": number,
  "cta": string
}""",
    },
    "future-me": {
        "instructions": """Project a warm, realistic, emotionally compelling vision of the user's future if they stay consistent
with the given goal at the given consistency %. Be specific but not absurd (no overpromising).""",
        "schema": """{
  "title": string,
  "message": string
}""",
    },
    "recap": {
        "instructions": """Summarize the user's day based on completed actions into a warm evening recap.
Make them feel proud. End with a small forward-looking note (not a new task, just warmth).""",
        "schema": """{
  "title": string,
  "message": string,
  "completed": [string],
  "total_points": number
}""",
    },
    "music": {
        "instructions": """Suggest a music mood/playlist type based on the user's current goal, mood, and activity.
Do not invent real song titles or artists — describe playlist vibe/genre instead.""",
        "schema": """{
  "playlist_mood": string,
  "message": string,
  "genre_tags": [string]
}""",
    },
    "reward": {
        "instructions": """Give the user an encouraging update on their progress toward their self-chosen reward.
Use their current points and the reward's point cost to motivate, never guilt.""",
        "schema": """{
  "reward": string,
  "points_remaining": number,
  "message": string
}""",
    },
    "memory/extract": {
        "instructions": """Extract durable, useful personalization facts from the raw user input (chat message, voice transcript, or journal entry).
Only extract facts likely to remain true for weeks/months (preferences, patterns, routines, emotional tendencies).
Do NOT extract one-off statements ("I'm tired today") as permanent memories.""",
        "schema": """{
  "memories": [string],
  "confidence": "low" | "medium" | "high"
}""",
    },
    "goals/progress": {
        "instructions": """Given a goal and current progress, generate an encouraging progress update with a realistic projection.
Projection must be a reasonable extrapolation from the given pace, not a wild guess.""",
        "schema": """{
  "goal": string,
  "progress": number,
  "message": string,
  "prediction": string
}""",
    },
}
