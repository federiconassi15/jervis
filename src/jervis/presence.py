from __future__ import annotations

import time


class PresenceManager:
    """Tracks lightweight local presence without redundant database round trips."""

    def __init__(self, state, timeout_seconds: int = 300) -> None:
        self.state = state
        self.timeout_seconds = max(30, int(timeout_seconds))

    def seen(self, user_id: str, source: str = "voice", confidence: float = 1.0) -> None:
        was_present = self.state.set_presence(user_id, source, confidence, True)
        if not was_present:
            self.state.event("presence_entered", "user=" + user_id + " source=" + source)

    def left(self, user_id: str, source: str = "timeout") -> None:
        rows = self.state.presence()
        existing = next((row for row in rows if str(row["user_id"]) == user_id), None)
        if existing is None or not bool(existing["present"]):
            return
        self.state.set_presence(
            user_id,
            source,
            float(existing["confidence"]),
            False,
        )
        self.state.event("presence_left", "user=" + user_id + " source=" + source)

    def sweep(self, now: float | None = None) -> list[str]:
        current = time.time() if now is None else float(now)
        left: list[str] = []
        for row in self.state.presence(present_only=True):
            if current - float(row["seen_at"]) >= self.timeout_seconds:
                user_id = str(row["user_id"])
                self.state.set_presence(
                    user_id,
                    "timeout",
                    float(row["confidence"]),
                    False,
                )
                self.state.event("presence_left", "user=" + user_id + " source=timeout")
                left.append(user_id)
        return left

    def active(self) -> list[dict[str, object]]:
        return [
            {
                "user_id": str(row["user_id"]),
                "name": str(row["name"]),
                "source": str(row["source"]),
                "confidence": float(row["confidence"]),
                "seen_at": float(row["seen_at"]),
            }
            for row in self.state.presence(present_only=True)
        ]
