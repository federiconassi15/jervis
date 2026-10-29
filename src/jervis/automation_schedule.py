"""Time-based extension for Jervis's existing approval-only automation engine.

All schedules dispatch symbolic events into AutomationStore.match_event().
No shell, network, notification, or plugin runs from this scheduler. A trusted
host must explicitly activate the rule and approve any resulting action.
"""
from __future__ import annotations

import hashlib
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .automation_engine import AutomationStore, Rule
from .capabilities import Principal


@dataclass(frozen=True)
class Schedule:
    kind: str  # "interval" or "daily_local"
    seconds: int = 0
    timezone: str = "UTC"
    hour: int = 0
    minute: int = 0


def _next_daily(sched: Schedule, now: float) -> float:
    try:
        zone = ZoneInfo(sched.timezone)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError("Unsupported timezone") from exc
    if not (0 <= sched.hour <= 23 and 0 <= sched.minute <= 59):
        raise ValueError("Invalid clock time")
    today = datetime.fromtimestamp(now, zone).date()
    for advance in range(5):
        day = today + timedelta(days=advance)
        candidate = datetime(day.year, day.month, day.day,
                             sched.hour, sched.minute, tzinfo=zone, fold=0)
        instant = candidate.timestamp()
        actual = datetime.fromtimestamp(instant, zone)
        # A spring-forward nonexistent local time is skipped, not silently
        # moved to a different wall-clock time.
        if (actual.hour, actual.minute) != (sched.hour, sched.minute):
            continue
        if instant > now:
            return instant
    raise RuntimeError("Could not find valid daily clock time")


def _next(sched: Schedule, now: float) -> float:
    if sched.kind == "interval":
        if not 60 <= sched.seconds <= 30 * 86400:
            raise ValueError("Intervals must be 60 seconds to 30 days")
        return now + sched.seconds
    if sched.kind == "daily_local":
        return _next_daily(sched, now)
    raise ValueError("Unrecognized schedule type")


class TimeAutomationStore(AutomationStore):
    """A composable time trigger feeding the existing automation approval queue."""

    def __init__(self, database):
        super().__init__(database)
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS time_rules("
            "rule_id TEXT PRIMARY KEY REFERENCES rules(id) ON DELETE CASCADE,"
            "kind TEXT NOT NULL,seconds INTEGER NOT NULL,timezone TEXT NOT NULL,"
            "hour INTEGER NOT NULL,minute INTEGER NOT NULL,next_due REAL NOT NULL)"
        )
        self.db.commit()

    def add_schedule(self, principal: Principal, schedule: Schedule,
                     *, action: str, capability: str, scope: str,
                     now: float | None = None) -> str:
        if not principal.authenticated or principal.role != "owner":
            raise PermissionError("Only an authenticated owner may add schedules")
        current = time.time() if now is None else now
        due = _next(schedule, current)
        # Fresh unique event names are known only to the host rule database.
        import uuid
        event = "schedule." + uuid.uuid4().hex
        rule = self.create(
            principal, Rule(event=event, action=action, capability=capability,
                            scope=scope, cooldown_seconds=30),
        )
        with self.db:
            self.db.execute(
                "INSERT INTO time_rules(rule_id,kind,seconds,timezone,hour,minute,next_due)"
                " VALUES(?,?,?,?,?,?,?)",
                (rule, schedule.kind, schedule.seconds, schedule.timezone,
                 schedule.hour, schedule.minute, due),
            )
        # Like ordinary rules, schedules are disabled by default.
        return rule

    def poll(self, principal: Principal, *, now: float | None = None,
             limit: int = 20) -> list[dict]:
        """Only inspect the invoking owner's schedules, with no implicit login."""
        if not principal.authenticated or principal.role != "owner":
            raise PermissionError("Authenticated owner required")
        if not 1 <= limit <= 100:
            raise ValueError("Invalid poll limit")
        current = time.time() if now is None else now
        rows = self.db.execute(
            "SELECT time_rules.*,rules.event FROM time_rules "
            "JOIN rules ON rules.id=time_rules.rule_id "
            "WHERE rules.owner=? AND rules.enabled=1 AND time_rules.next_due<=? "
            "ORDER BY time_rules.next_due,rule_id LIMIT ?",
            (principal.user_id, current, limit),
        ).fetchall()
        ready = []
        for row in rows:
            scheduled = row["next_due"]
            # Same scheduled occurrence always produces the same event ID,
            # so a crash between dispatch and update cannot double-deliver.
            receipt = hashlib.sha256(
                (row["rule_id"] + ":" + str(scheduled)).encode("ascii")
            ).hexdigest()[:32]
            ready.extend(self.match_event(
                principal, event_id=receipt, event_code=row["event"],
                now=current,
            ))
            trigger = Schedule(kind=row["kind"], seconds=row["seconds"],
                               timezone=row["timezone"], hour=row["hour"],
                               minute=row["minute"])
            next_due = _next(trigger, current)  # Skip missed-run storms.
            with self.db:
                self.db.execute(
                    "UPDATE time_rules SET next_due=? WHERE rule_id=? "
                    "AND next_due=?",
                    (next_due, row["rule_id"], scheduled),
                )
        return ready
