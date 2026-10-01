from __future__ import annotations

import time
from datetime import datetime, time as clock
from typing import Callable


def _clock(value: str) -> clock:
    hour, minute = map(int, value.split(":"))
    return clock(hour, minute)


class ProactiveEngine:
    def __init__(self, state, config: dict, announce: Callable[[str], None]) -> None:
        self.state = state
        self.config = config
        self.announce = announce
        self.last: dict[str, float] = {}

    def quiet_now(self) -> bool:
        start = _clock(self.config["quiet_hours_start"])
        end = _clock(self.config["quiet_hours_end"])
        now = datetime.now().time()
        return start <= now < end if start <= end else now >= start or now < end

    def alert(self, key: str, message: str, cooldown: int = 900) -> bool:
        if not self.config.get("enabled", True) or self.quiet_now():
            return False
        now = time.time()
        if now - self.last.get(key, 0.0) < max(0, int(cooldown)):
            return False
        self.last[key] = now
        self.state.event("proactive_alert", key)
        self.announce(message)
        return True

    def queue(
        self,
        key: str,
        message: str,
        user_id: str | None = None,
    ) -> int:
        notification_id = self.state.notify(key, message, user_id)
        self.state.event("proactive_queued", key)
        return notification_id

    def tick(self) -> bool:
        if not self.config.get("enabled", True) or self.quiet_now():
            return False

        present = self.state.presence(present_only=True)
        if not present:
            return False

        user_id = str(present[0]["user_id"])
        row = self.state.next_notification(user_id)
        if row is None:
            return False

        self.state.mark_notification(int(row["id"]))
        self.state.event("proactive_delivered", str(row["key"]))
        self.announce(str(row["text"]))
        return True
