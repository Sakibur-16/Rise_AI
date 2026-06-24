"""
Memory Engine.

Lightweight in-memory store for user personalization facts.
This is intentionally NOT a database — out of scope per the spec.
Swap this module's internals for a real DB call later; nothing else
in the app needs to change since routes only call get_memories/add_memories.
"""

_store: dict[str, set[str]] = {}


def get_memories(user_id: str | None) -> list[str]:
    if not user_id:
        return []
    return sorted(_store.get(user_id, set()))


def add_memories(user_id: str | None, new_memories: list[str]) -> list[str]:
    if not user_id or not new_memories:
        return get_memories(user_id)

    existing = _store.setdefault(user_id, set())
    for m in new_memories:
        if m and m.strip():
            existing.add(m.strip())

    return sorted(existing)


def clear_memories(user_id: str) -> None:
    _store.pop(user_id, None)
