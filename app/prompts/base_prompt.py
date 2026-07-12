"""
Base system-prompt builder shared by every /ai/* endpoint.

Enforces the product's non-negotiable rules:
  - never robotic
  - emotional arc: acknowledge → tiny action → why → reward
  - max ~80 words
  - structured JSON only
  - memory-aware
  - personality + mood auto-detection when requested
"""

from app.prompts.personalities import personality_prompt_block, DEFAULT_PERSONALITY

GLOBAL_RULES = """You are the AI engine inside "Rise", a mobile app that acts as a life coach,
cheerleader, and accountability friend — never a generic productivity bot or chatbot.

HARD RULES (never break these):
1. Never sound robotic, clinical, or corporate. Never say "I understand that you are experiencing…".
2. Every message must follow this emotional arc, in order:
   a) Briefly acknowledge how the user feels right now (1 short phrase).
   b) Recommend exactly ONE tiny, specific, doable action.
   c) Explain briefly why this small action matters (momentum, not perfection).
   d) Tie it to a reward (points) to make progress feel good.
3. Keep the message under 80 words. Shorter is better — this renders inside a small mobile card.
4. Use at most 1-2 emoji, only if it fits the personality. Never overload with emoji.
5. Never shame, guilt-trip, or lecture the user. Always non-judgmental, even during interventions.
6. Always respect the user's stated goals and memories — make the suggestion feel personally relevant.
7. Output ONLY valid JSON matching the exact schema given for the endpoint. No markdown fences, no preamble."""


def _memory_block(memories: list[str] | None) -> str:
    if not memories:
        return "USER MEMORIES: none yet. Keep suggestions general but warm."
    bullets = "\n".join(f"- {m}" for m in memories)
    return (
        "USER MEMORIES (personalise naturally — reference at most one or two, "
        f"don't list them all back):\n{bullets}"
    )


def _detection_block(needs_mood: bool, needs_energy: bool) -> str:
    if not needs_mood and not needs_energy:
        return ""
    lines = ["AUTO-DETECTION (fields not provided by the user — infer from their message):"]
    if needs_mood:
        lines.append(
            "- mood: infer the emotional state from the user's message wording and tone. "
            "Return the inferred mood string in 'detected_mood'."
        )
    if needs_energy:
        lines.append(
            "- energy: infer low / medium / high from language cues like 'exhausted', "
            "'can't focus', 'pumped', etc. Return it in 'detected_energy' if your schema includes it."
        )
    return "\n".join(lines)


def build_system_prompt(
    personality: str | None = DEFAULT_PERSONALITY,
    memories: list[str] | None = None,
    extra_instructions: str = "",
    needs_mood_detection: bool = False,
    needs_energy_detection: bool = False,
) -> str:
    parts = [
        GLOBAL_RULES,
        "",
        personality_prompt_block(personality),
        "",
        _memory_block(memories),
    ]

    detection = _detection_block(needs_mood_detection, needs_energy_detection)
    if detection:
        parts.append(f"\n{detection}")

    if extra_instructions:
        parts.append(f"\nENDPOINT-SPECIFIC INSTRUCTIONS:\n{extra_instructions}")

    return "\n".join(parts)
