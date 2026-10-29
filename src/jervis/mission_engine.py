"""Durable, capability-checked mission queue (8.2 experimental foundation).

No shell commands, network calls, plugin imports or model output execute here.
Trusted callers explicitly register handlers. Non-idempotent interrupted steps
remain blocked and cannot be silently replayed after a process crash.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Any

from .capabilities import CapabilityGrant, Principal, authorize

_ACTION = re.compile(r"[a-z][a-z0-9_.-]{0,79}\Z")
_MAX_STEPS = 32


@dataclass(frozen=True)
class MissionStep:
    action: str
    capability: str
    scope: str
    payload: dict
    idempotent: bool = False


class MissionStore:
    """Single-host SQLite queue; not a distributed exactly-once executor."""

    def __init__(self, database: Path):
        path = Path(database)
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if path.is_symlink():
            raise PermissionError("Mission state path is a symlink")
        if not path.exists():
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
        if os.name != "nt":
            path.chmod(0o600)
        self.db = sqlite3.connect(path, timeout=5, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA busy_timeout=5000")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS missions(
                id TEXT PRIMARY KEY,
                owner TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                created REAL NOT NULL,
                updated REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS steps(
                id TEXT PRIMARY KEY,
                mission_id TEXT NOT NULL REFERENCES missions(id) ON DELETE CASCADE,
                position INTEGER NOT NULL,
                action TEXT NOT NULL,
                capability TEXT NOT NULL,
                scope TEXT NOT NULL,
                payload TEXT NOT NULL,
                idempotent INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                result TEXT,
                UNIQUE(mission_id, position)
            );
        """)

    def create(self, principal: Principal, steps: tuple[MissionStep, ...]) -> str:
        if not principal.authenticated or principal.role != "owner":
            raise PermissionError("Only authenticated owners can create missions")
        if not steps or len(steps) > _MAX_STEPS:
            raise ValueError("Mission must have 1..32 steps")
        for step in steps:
            if not _ACTION.fullmatch(step.action):
                raise ValueError("Invalid action identifier")
            if not isinstance(step.payload, dict):
                raise ValueError("Step payload must be a JSON object")
            encoded = json.dumps(step.payload, allow_nan=False)
            if len(encoded) > 16384 or len(step.scope) > 2048:
                raise ValueError("Mission step exceeds safe bounds")
        mission_id = uuid.uuid4().hex
        now = time.time()
        with self.db:
            self.db.execute(
                "INSERT INTO missions(id,owner,status,created,updated) VALUES(?,?,?,?,?)",
                (mission_id, principal.user_id, "queued", now, now),
            )
            for position, step in enumerate(steps):
                self.db.execute(
                    "INSERT INTO steps(id,mission_id,position,action,capability,scope,"
                    "payload,idempotent) VALUES(?,?,?,?,?,?,?,?)",
                    (uuid.uuid4().hex, mission_id, position, step.action,
                     step.capability, step.scope, json.dumps(step.payload),
                     int(step.idempotent)),
                )
        return mission_id

    def recover(self) -> tuple[int, int]:
        """Only replay explicitly idempotent running steps; block the others."""
        with self.db:
            safe = self.db.execute(
                "UPDATE steps SET status='queued' "
                "WHERE status='running' AND idempotent=1"
            ).rowcount
            blocked = self.db.execute(
                "UPDATE steps SET status='blocked' "
                "WHERE status='running' AND idempotent=0"
            ).rowcount
            self.db.execute(
                "UPDATE missions SET status='blocked' WHERE id IN "
                "(SELECT mission_id FROM steps WHERE status='blocked')"
            )
        return safe, blocked

    def describe(self, mission_id: str, principal: Principal) -> dict:
        mission = self.db.execute(
            "SELECT * FROM missions WHERE id=? AND owner=?",
            (mission_id, principal.user_id),
        ).fetchone()
        if mission is None or not principal.authenticated:
            raise PermissionError("Mission unavailable")
        steps = self.db.execute(
            "SELECT id,position,action,capability,status,idempotent FROM steps "
            "WHERE mission_id=? ORDER BY position", (mission_id,)
        ).fetchall()
        return {
            "id": mission_id, "status": mission["status"],
            "steps": [dict(row) for row in steps],
        }

    def execute_next(self, mission_id: str, principal: Principal,
                     registry: dict[str, Callable[[dict], Any]], *,
                     grants: tuple[CapabilityGrant, ...] = (),
                     fresh_auth: bool = False) -> str:
        """Executes exactly one trusted handler after a fresh policy decision."""
        if not principal.authenticated:
            raise PermissionError("Authenticated principal required")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            mission = self.db.execute(
                "SELECT owner,status FROM missions WHERE id=?", (mission_id,)
            ).fetchone()
            if mission is None or mission["owner"] != principal.user_id:
                raise PermissionError("Mission unavailable")
            if mission["status"] in {"blocked", "cancelled", "completed"}:
                self.db.execute("COMMIT")
                return mission["status"]
            step = self.db.execute(
                "SELECT * FROM steps WHERE mission_id=? AND status!='completed' "
                "ORDER BY position LIMIT 1", (mission_id,)
            ).fetchone()
            if step is None:
                self.db.execute("UPDATE missions SET status='completed' WHERE id=?",
                                (mission_id,))
                self.db.execute("COMMIT")
                return "completed"
            if step["status"] not in {"queued", "waiting_approval"}:
                self.db.execute("COMMIT")
                return step["status"]
            decision = authorize(
                principal, step["capability"], scope=step["scope"],
                grants=grants, fresh_auth=fresh_auth,
            )
            if not decision.permitted:
                self.db.execute("UPDATE steps SET status='waiting_approval' WHERE id=?",
                                (step["id"],))
                self.db.execute(
                    "UPDATE missions SET status='waiting_approval' WHERE id=?",
                    (mission_id,),
                )
                self.db.execute("COMMIT")
                return "waiting_approval"
            handler = registry.get(step["action"])
            if handler is None:
                self.db.execute("ROLLBACK")
                raise ValueError("Action has no trusted registered handler")
            self.db.execute("UPDATE steps SET status='running' WHERE id=?",
                            (step["id"],))
            self.db.execute("UPDATE missions SET status='running',updated=? WHERE id=?",
                            (time.time(), mission_id))
            self.db.execute("COMMIT")
        except BaseException:
            if self.db.in_transaction:
                self.db.execute("ROLLBACK")
            raise

        try:
            # Trusted handler must implement idempotency for external actions.
            value = handler(json.loads(step["payload"]))
            result = json.dumps(value, allow_nan=False)
            if len(result) > 16384:
                raise ValueError("Handler output exceeds safe limit")
        except Exception:
            # Do not persist handler exception text: it may contain secrets.
            with self.db:
                self.db.execute(
                    "UPDATE steps SET status='failed',result=? WHERE id=?",
                    ('{"error":"handler_failed"}', step["id"]),
                )
                self.db.execute(
                    "UPDATE missions SET status='failed',updated=? WHERE id=?",
                    (time.time(), mission_id),
                )
            return "failed"

        with self.db:
            self.db.execute(
                "UPDATE steps SET status='completed',result=? WHERE id=?",
                (result, step["id"]),
            )
            remaining = self.db.execute(
                "SELECT COUNT(*) FROM steps WHERE mission_id=? AND status!='completed'",
                (mission_id,),
            ).fetchone()[0]
            status = "completed" if remaining == 0 else "queued"
            self.db.execute(
                "UPDATE missions SET status=?,updated=? WHERE id=?",
                (status, time.time(), mission_id),
            )
        return status

    def cancel(self, mission_id: str, principal: Principal) -> bool:
        if not principal.authenticated:
            return False
        with self.db:
            result = self.db.execute(
                "UPDATE missions SET status='cancelled' "
                "WHERE id=? AND owner=? AND status IN ('queued','waiting_approval')",
                (mission_id, principal.user_id),
            )
        return result.rowcount == 1

    def close(self):
        self.db.close()
