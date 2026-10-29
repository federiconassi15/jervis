"""Jervis 8.2 automation scheduler: bounded, durable, approval-first.

Schedules produce durable work items only. They NEVER execute shell commands,
plugin code, network requests, or model-supplied actions. A separately audited
Mission Control executor must reauthorize each actual operation.
"""
from __future__ import annotations

import json
import re
import sqlite3
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .capabilities import Principal

_ID_RE = re.compile(r"[a-z][a-z0-9_.-]{0,79}\Z")
_MAX_RULES_PER_OWNER = 128
_MAX_CATCHUP = 1
_MIN_INTERVAL = 60
_MAX_INTERVAL = 30 * 86400


@dataclass(frozen=True)
class Trigger:
    kind: str                   # interval, daily_local, event
    interval_seconds: int = 0
    timezone_name: str = "UTC"
    hour: int = 0
    minute: int = 0
    event_kind: str = ""


@dataclass(frozen=True)
class Automation:
    trigger: Trigger
    action: str                 # symbolic trusted action identifier
    capability: str
    scope: str
    payload: dict
    idempotent: bool = False


def _next_daily(now: float, trigger: Trigger) -> float:
    """Next matching local wall-clock occurrence, skipping nonexistent times.

    Ambiguous times use the first occurrence, and each day executes at most once.
    """
    try:
        zone = ZoneInfo(trigger.timezone_name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError("Unknown automation timezone") from exc
    if not 0 <= trigger.hour <= 23 or not 0 <= trigger.minute <= 59:
        raise ValueError("Invalid daily execution clock")
    today = datetime.fromtimestamp(now, zone).date()
    for delta in range(0, 5):
        day = today + timedelta(days=delta)
        local = datetime(
            day.year, day.month, day.day,
            trigger.hour, trigger.minute, tzinfo=zone, fold=0,
        )
        # Detect spring-forward nonexistent local times by roundtripping.
        instant = local.timestamp()
        roundtrip = datetime.fromtimestamp(instant, zone)
        if (roundtrip.hour, roundtrip.minute) != (trigger.hour, trigger.minute):
            continue
        if instant > now:
            return instant
    raise RuntimeError("Unable to schedule daily event")


def _validate_trigger(trigger: Trigger) -> None:
    if trigger.kind == "interval":
        if not _MIN_INTERVAL <= trigger.interval_seconds <= _MAX_INTERVAL:
            raise ValueError("Interval must be 60 seconds to 30 days")
    elif trigger.kind == "daily_local":
        _next_daily(time.time(), trigger)
    elif trigger.kind == "event":
        if not _ID_RE.fullmatch(trigger.event_kind):
            raise ValueError("Invalid subscribed event identifier")
    else:
        raise ValueError("Unsupported trigger type")


def _check_owner(principal: Principal) -> None:
    if not principal.authenticated or not principal.user_id or principal.role != "owner":
        raise PermissionError("Only an authenticated owner can manage automations")


def _encode(automation: Automation) -> str:
    _validate_trigger(automation.trigger)
    if not _ID_RE.fullmatch(automation.action):
        raise ValueError("Invalid registered action name")
    if not _ID_RE.fullmatch(automation.capability):
        raise ValueError("Invalid capability")
    if not automation.scope or len(automation.scope) > 2048:
        raise ValueError("Explicit bounded resource scope required")
    if not isinstance(automation.payload, dict):
        raise ValueError("Automation payload must be an object")
    data = {
        "trigger": vars_from_trigger(automation.trigger),
        "action": automation.action,
        "capability": automation.capability,
        "scope": automation.scope,
        "payload": automation.payload,
        "idempotent": automation.idempotent,
    }
    encoded = json.dumps(data, separators=(",", ":"), allow_nan=False)
    if len(encoded) > 16384:
        raise ValueError("Automation too large")
    return encoded


def vars_from_trigger(trigger: Trigger) -> dict:
    return {
        "kind": trigger.kind, "interval_seconds": trigger.interval_seconds,
        "timezone_name": trigger.timezone_name, "hour": trigger.hour,
        "minute": trigger.minute, "event_kind": trigger.event_kind,
    }


class AutomationStore:
    """Schedules and records work; execution lives outside this module."""

    def __init__(self, path: Path):
        path = Path(path)
        if path.is_symlink():
            raise PermissionError("Automation database must not be a symlink")
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=5, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA busy_timeout=5000")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS automation_rules (
                id TEXT PRIMARY KEY,
                owner TEXT NOT NULL,
                definition TEXT NOT NULL,
                next_due REAL,
                enabled INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_automation_due
                ON automation_rules(enabled,next_due);
            CREATE TABLE IF NOT EXISTS automation_runs (
                id TEXT PRIMARY KEY,
                rule_id TEXT NOT NULL REFERENCES automation_rules(id)
                    ON DELETE CASCADE,
                trigger_key TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                created_at REAL NOT NULL,
                UNIQUE(rule_id,trigger_key)
            );
            CREATE INDEX IF NOT EXISTS idx_automation_runs
                ON automation_runs(status,created_at);
        """)

    def create(self, principal: Principal, automation: Automation, *,
               now: float | None = None) -> str:
        _check_owner(principal)
        encoded = _encode(automation)
        ts = time.time() if now is None else now
        if automation.trigger.kind == "interval":
            due = ts + automation.trigger.interval_seconds
        elif automation.trigger.kind == "daily_local":
            due = _next_daily(ts, automation.trigger)
        else:
            due = None
        rule_id = uuid.uuid4().hex
        self.db.execute("BEGIN IMMEDIATE")
        try:
            count = self.db.execute(
                "SELECT COUNT(*) FROM automation_rules WHERE owner=?",
                (principal.user_id,),
            ).fetchone()[0]
            if count >= _MAX_RULES_PER_OWNER:
                raise ValueError("Automation rule limit reached")
            self.db.execute(
                "INSERT INTO automation_rules(id,owner,definition,next_due,enabled)"
                " VALUES(?,?,?,?,0)",
                (rule_id, principal.user_id, encoded, due),
            )
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise
        return rule_id

    def set_enabled(self, principal: Principal, rule_id: str, enabled: bool) -> None:
        _check_owner(principal)
        with self.db:
            found = self.db.execute(
                "UPDATE automation_rules SET enabled=? WHERE id=? AND owner=?",
                (int(bool(enabled)), rule_id, principal.user_id),
            ).rowcount
        if not found:
            raise PermissionError("Automation unavailable")

    def due(self, *, now: float | None = None, limit: int = 20) -> list[str]:
        """Enqueue due runs, skipping missed interval backlog (one per rule)."""
        if not 1 <= limit <= 100:
            raise ValueError("Invalid poll limit")
        ts = time.time() if now is None else now
        result = []
        self.db.execute("BEGIN IMMEDIATE")
        try:
            rules = self.db.execute(
                "SELECT id,definition,next_due FROM automation_rules "
                "WHERE enabled=1 AND next_due IS NOT NULL AND next_due<=? "
                "ORDER BY next_due,id LIMIT ?", (ts, limit),
            ).fetchall()
            for row in rules:
                obj = json.loads(row["definition"])
                trigger = Trigger(**obj["trigger"])
                key = "time:" + str(int(row["next_due"]))
                identifier = uuid.uuid4().hex
                found = self.db.execute(
                    "INSERT OR IGNORE INTO automation_runs(id,rule_id,trigger_key,created_at)"
                    " VALUES(?,?,?,?)",
                    (identifier, row["id"], key, ts),
                ).rowcount
                if found:
                    result.append(identifier)
                if trigger.kind == "interval":
                    # No unbounded wake-up storm after power loss or long downtime.
                    next_due = ts + trigger.interval_seconds
                elif trigger.kind == "daily_local":
                    next_due = _next_daily(ts, trigger)
                else:
                    raise ValueError("Unexpected timed trigger")
                self.db.execute(
                    "UPDATE automation_rules SET next_due=? WHERE id=?",
                    (next_due, row["id"]),
                )
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise
        return result

    def on_event(self, event_kind: str, event_id: str, *, now: float | None = None,
                 limit: int = 100) -> list[str]:
        """Ingest a trusted system event with a unique id; replays are ignored."""
        if not _ID_RE.fullmatch(event_kind) or not re.fullmatch(r"[0-9a-f]{32}", event_id):
            raise ValueError("Event type/identifier malformed")
        if not 1 <= limit <= 100:
            raise ValueError("Invalid event limit")
        ts = time.time() if now is None else now
        created = []
        self.db.execute("BEGIN IMMEDIATE")
        try:
            rules = self.db.execute(
                "SELECT id,definition FROM automation_rules WHERE enabled=1 ORDER BY id"
            ).fetchall()
            for rule in rules:
                if len(created) >= limit:
                    break
                trigger = Trigger(**json.loads(rule["definition"])["trigger"])
                if trigger.kind != "event" or trigger.event_kind != event_kind:
                    continue
                run_id = uuid.uuid4().hex
                inserted = self.db.execute(
                    "INSERT OR IGNORE INTO automation_runs("
                    "id,rule_id,trigger_key,created_at) VALUES(?,?,?,?)",
                    (run_id, rule["id"], "event:" + event_id, ts),
                ).rowcount
                if inserted:
                    created.append(run_id)
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise
        return created

    def pending(self, principal: Principal, *, limit: int = 20) -> list[dict]:
        if not principal.authenticated or not 1 <= limit <= 100:
            raise PermissionError("Authentication or valid limit required")
        rows = self.db.execute(
            "SELECT runs.id,runs.rule_id,runs.trigger_key,runs.status,"
            "rules.definition FROM automation_runs runs "
            "JOIN automation_rules rules ON rules.id=runs.rule_id "
            "WHERE rules.owner=? AND runs.status='queued' "
            "ORDER BY runs.created_at,runs.id LIMIT ?",
            (principal.user_id, limit),
        )
        return [{
            "id": r["id"], "rule_id": r["rule_id"],
            "trigger_key": r["trigger_key"], "status": r["status"],
            "action": json.loads(r["definition"])["action"],
            "capability": json.loads(r["definition"])["capability"],
        } for r in rows]

    def complete(self, principal: Principal, run_id: str) -> None:
        """Mark completed only after an audited executor confirmed the action."""
        _check_owner(principal)
        with self.db:
            updated = self.db.execute(
                "UPDATE automation_runs SET status='completed' "
                "WHERE id=? AND status='queued' AND rule_id IN "
                "(SELECT id FROM automation_rules WHERE owner=?)",
                (run_id, principal.user_id),
            ).rowcount
        if not updated:
            raise ValueError("Run cannot be completed")

    def close(self) -> None:
        self.db.close()
