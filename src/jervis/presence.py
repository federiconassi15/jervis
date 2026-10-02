from __future__ import annotations

import time


class PresenceManager:
    """Tracks room presence, returns, and active-speaker handoffs."""

    def __init__(
        self,
        state,
        timeout_seconds: int = 300,
        return_window_seconds: int = 1800,
    ) -> None:
        self.state = state
        self.timeout_seconds = max(30, int(timeout_seconds))
        self.return_window_seconds = max(
            self.timeout_seconds,
            int(return_window_seconds),
        )

    def seen(
        self,
        user_id: str,
        source: str = "voice",
        confidence: float = 1.0,
    ) -> None:
        now = time.time()
        existing = next(
            (
                row
                for row in self.state.presence()
                if str(row["user_id"]) == user_id
            ),
            None,
        )
        previous_active = self.state.get_kv("presence.active_user")
        was_present = self.state.set_presence(
            user_id,
            source,
            confidence,
            True,
        )

        if not was_present:
            returned = bool(
                existing
                and now - float(existing["seen_at"])
                <= self.return_window_seconds
            )
            transition = "returned" if returned else "entered"
            self.state.record_presence_transition(
                user_id,
                transition,
                source,
                confidence,
            )
            self.state.event(
                "presence_" + transition,
                "user=" + user_id + " source=" + source,
            )

        if previous_active != user_id:
            if previous_active:
                self.state.event(
                    "presence_handoff",
                    "from=" + str(previous_active) + " to=" + user_id,
                )
            self.state.set_kv("presence.active_user", user_id)

    def left(self, user_id: str, source: str = "timeout") -> None:
        rows = self.state.presence()
        existing = next(
            (row for row in rows if str(row["user_id"]) == user_id),
            None,
        )
        if existing is None or not bool(existing["present"]):
            return
        confidence = float(existing["confidence"])
        self.state.set_presence(user_id, source, confidence, False)
        self.state.record_presence_transition(
            user_id,
            "left",
            source,
            confidence,
        )
        self.state.event(
            "presence_left",
            "user=" + user_id + " source=" + source,
        )
        if self.state.get_kv("presence.active_user") == user_id:
            self.state.delete_kv("presence.active_user")

    def sweep(self, now: float | None = None) -> list[str]:
        current = time.time() if now is None else float(now)
        left: list[str] = []
        for row in self.state.presence(present_only=True):
            if current - float(row["seen_at"]) >= self.timeout_seconds:
                user_id = str(row["user_id"])
                confidence = float(row["confidence"])
                self.state.set_presence(
                    user_id,
                    "timeout",
                    confidence,
                    False,
                )
                self.state.record_presence_transition(
                    user_id,
                    "left",
                    "timeout",
                    confidence,
                )
                self.state.event(
                    "presence_left",
                    "user=" + user_id + " source=timeout",
                )
                if self.state.get_kv("presence.active_user") == user_id:
                    self.state.delete_kv("presence.active_user")
                left.append(user_id)
        return left

    def active_user(self) -> str | None:
        value = self.state.get_kv("presence.active_user")
        return None if value is None else str(value)

    def active(self) -> list[dict[str, object]]:
        active_user = self.active_user()
        return [
            {
                "user_id": str(row["user_id"]),
                "name": str(row["name"]),
                "source": str(row["source"]),
                "confidence": float(row["confidence"]),
                "seen_at": float(row["seen_at"]),
                "active": str(row["user_id"]) == active_user,
            }
            for row in self.state.presence(present_only=True)
        ]
