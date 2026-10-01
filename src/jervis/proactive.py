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

    def queue(self, key: str, message: str) -> None:
        self.state.set_kv(
            "proactive.pending." + key,
            {"message": message, "created_at": time.time()},
        )
        self.state.event("proactive_queued", key)
