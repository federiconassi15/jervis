from __future__ import annotations

import json
import time
from datetime import datetime, time as clock
from pathlib import Path
from typing import Callable

from .openclaw_setup import doctor as openclaw_doctor
from .openclaw_setup import find_openclaw


def _clock(value: str) -> clock:
    hour, minute = map(int, value.split(":"))
    return clock(hour, minute)


class ProactiveEngine:
    def __init__(
        self,
        state,
        config: dict,
        announce: Callable[[str], None],
    ) -> None:
        self.state = state
        self.config = config
        self.announce = announce
        self.last: dict[str, float] = {}

    def quiet_now(self) -> bool:
        start = _clock(self.config["quiet_hours_start"])
        end = _clock(self.config["quiet_hours_end"])
        now = datetime.now().time()
        return start <= now < end if start <= end else now >= start or now < end

    def alert(
        self,
        key: str,
        message: str,
        cooldown: int = 900,
        *,
        reason: str = "",
    ) -> bool:
        if not self.config.get("enabled", True) or self.quiet_now():
            return False
        now = time.time()
        if now - self.last.get(key, 0.0) < max(0, int(cooldown)):
            return False
        self.last[key] = now
        detail = key + ((" reason=" + reason) if reason else "")
        self.state.event("proactive_alert", detail)
        self.announce(message)
        return True

    def queue(
        self,
        key: str,
        message: str,
        user_id: str | None = None,
        *,
        priority: int = 0,
        ttl_seconds: int | None = None,
        not_before: float | None = None,
        reason: str = "",
    ) -> int:
        expires_at = (
            None
            if ttl_seconds is None
            else time.time() + max(1, int(ttl_seconds))
        )
        notification_id = self.state.notify(
            key,
            message,
            user_id,
            priority=int(priority),
            expires_at=expires_at,
            not_before=not_before,
            reason=reason,
        )
        self.state.event(
            "proactive_queued",
            key
            + " priority="
            + str(int(priority))
            + ((" reason=" + reason) if reason else ""),
        )
        return notification_id

    def _condition_value(self, kind: str, spec: dict) -> tuple[bool, object]:
        if kind == "file_exists":
            raw = str(spec.get("path") or "").strip()
            exists = bool(raw) and Path(raw).expanduser().exists()
            return exists, {"exists": exists, "path": raw}

        if kind == "openclaw_ready":
            cli = find_openclaw()
            if cli is None:
                return False, {"installed": False, "healthy": False}
            try:
                healthy, detail = openclaw_doctor(cli)
            except Exception as exc:
                return False, {
                    "installed": True,
                    "healthy": False,
                    "detail": type(exc).__name__,
                }
            return bool(healthy), {
                "installed": True,
                "healthy": bool(healthy),
                "detail": str(detail)[-300:],
            }

        if kind == "state_equals":
            key = str(spec.get("key") or "")
            expected = spec.get("value")
            current = self.state.get_kv(key)
            return current == expected, {
                "key": key,
                "current": current,
                "expected": expected,
            }

        return False, {"unsupported": kind}

    def evaluate_conditions(self) -> int:
        now = time.time()
        expired = self.state.expire_condition_watches(now)
        if expired:
            self.state.event(
                "condition_watch_expired",
                "count=" + str(expired),
            )

        fired = 0
        for row in self.state.due_condition_watches(now=now, limit=25):
            try:
                spec = json.loads(str(row["spec"]))
                if not isinstance(spec, dict):
                    spec = {}
            except json.JSONDecodeError:
                spec = {}

            met, value = self._condition_value(str(row["kind"]), spec)
            self.state.mark_condition_checked(
                int(row["id"]),
                value,
                now=now,
            )
            if not met:
                continue

            self.state.notify(
                str(row["key"]),
                str(row["message"]),
                row["user_id"],
                priority=int(row["priority"]),
                reason=str(row["reason"] or "A local condition became true."),
            )
            self.state.complete_condition_watch(int(row["id"]))
            self.state.event(
                "condition_watch_fired",
                "id="
                + str(row["id"])
                + " kind="
                + str(row["kind"]),
            )
            fired += 1
        return fired

    def tick(self) -> bool:
        if not self.config.get("enabled", True):
            return False

        self.evaluate_conditions()

        expired = self.state.expire_notifications()
        if expired:
            self.state.event(
                "proactive_expired",
                "count=" + str(expired),
            )

        if self.quiet_now():
            return False

        present = self.state.presence(present_only=True)
        if not present:
            return False

        active_user = self.state.get_kv("presence.active_user")
        user_id = (
            str(active_user)
            if active_user
            else str(present[0]["user_id"])
        )
        now = time.time()
        busy_until = self.state.get_kv(
            "proactive.busy_until." + user_id,
            0,
        )
        try:
            busy_until = float(busy_until or 0)
        except (TypeError, ValueError):
            busy_until = 0.0
        if busy_until > now:
            return False
        if busy_until:
            self.state.delete_kv("proactive.busy_until." + user_id)

        row = self.state.next_notification(user_id, now=now)
        if row is None:
            return False

        self.state.mark_notification(int(row["id"]))
        detail = (
            str(row["key"])
            + " priority="
            + str(row["priority"])
            + (
                " reason=" + str(row["reason"])
                if str(row["reason"])
                else ""
            )
        )
        self.state.event("proactive_delivered", detail)
        self.state.set_kv(
            "proactive.last_delivery." + user_id,
            {
                "key": str(row["key"]),
                "text": str(row["text"]),
                "reason": str(row["reason"] or ""),
                "priority": int(row["priority"]),
                "delivered_at": time.time(),
            },
        )
        self.announce(str(row["text"]))
        return True
