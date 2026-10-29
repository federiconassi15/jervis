"""Durable, bounded declarative automation evaluator for Jervis 8.2.

No dynamic code, cron parsing, shell execution, network calls or model output.
Matched rules produce *pending requests*; only the authorized mission executor
may later perform an operation after its own capability checks.
"""
from __future__ import annotations

import os
import re
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from .capabilities import Principal

_NAME = re.compile(r"[a-z][a-z0-9_.-]{0,79}\Z")


@dataclass(frozen=True)
class Rule:
    event: str
    action: str
    capability: str
    scope: str
    cooldown_seconds: int = 60


class AutomationStore:
    def __init__(self, database: Path):
        path = Path(database)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if path.is_symlink():
            raise PermissionError("Refusing symlinked automation state")
        if not path.exists():
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
        self.db = sqlite3.connect(path, timeout=5, isolation_level="DEFERRED")
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA busy_timeout=5000")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS rules(
                id TEXT PRIMARY KEY, owner TEXT NOT NULL, event TEXT NOT NULL,
                action TEXT NOT NULL, capability TEXT NOT NULL, scope TEXT NOT NULL,
                cooldown INTEGER NOT NULL, enabled INTEGER NOT NULL DEFAULT 0,
                last_fired REAL
            );
            CREATE TABLE IF NOT EXISTS event_receipts(
                owner TEXT NOT NULL, event_id TEXT NOT NULL,
                recorded REAL NOT NULL,
                PRIMARY KEY(owner,event_id)
            );
            CREATE TABLE IF NOT EXISTS pending_actions(
                id TEXT PRIMARY KEY, rule_id TEXT NOT NULL,
                event_id TEXT NOT NULL,
                owner TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'waiting_approval',
                created REAL NOT NULL,
                UNIQUE(rule_id,event_id)
            );
        """)
        self.db.commit()

    def create(self, principal: Principal, rule: Rule) -> str:
        if not principal.authenticated or principal.role != "owner":
            raise PermissionError("Authenticated owner required")
        if not _NAME.fullmatch(rule.event) or not _NAME.fullmatch(rule.action):
            raise ValueError("Invalid event/action name")
        if not 30 <= rule.cooldown_seconds <= 86400 or not 1 <= len(rule.scope) <= 2048:
            raise ValueError("Automation bounds exceeded")
        key = uuid.uuid4().hex
        with self.db:
            self.db.execute(
                "INSERT INTO rules(id,owner,event,action,capability,scope,cooldown)"
                " VALUES(?,?,?,?,?,?,?)",
                (key,principal.user_id,rule.event,rule.action,
                 rule.capability,rule.scope,rule.cooldown_seconds),
            )
        return key

    def set_enabled(self, principal: Principal, rule_id: str, enabled: bool) -> bool:
        """Rule changes require explicit authenticated owner action."""
        if not principal.authenticated or principal.role != "owner":
            raise PermissionError("Authenticated owner required")
        with self.db:
            result = self.db.execute(
                "UPDATE rules SET enabled=? WHERE id=? AND owner=?",
                (int(bool(enabled)),rule_id,principal.user_id),
            )
        return result.rowcount == 1

    def match_event(self, principal: Principal, *, event_id: str,
                    event_code: str, now: float | None = None,
                    dry_run: bool = False) -> list[dict]:
        """Create at most one pending approval per unique owner/event/rule."""
        if not principal.authenticated or principal.role != "owner":
            raise PermissionError("Authenticated owner required")
        if not re.fullmatch(r"[0-9a-f]{32}", event_id):
            raise ValueError("Invalid canonical event identifier")
        if not _NAME.fullmatch(event_code):
            raise ValueError("Invalid event code")
        current = time.time() if now is None else float(now)
        candidates = list(self.db.execute(
            "SELECT id,action,capability,scope,cooldown,last_fired FROM rules "
            "WHERE owner=? AND event=? AND enabled=1",
            (principal.user_id,event_code),
        ))
        matches = [
            {"rule_id":row["id"],"action":row["action"],
             "capability":row["capability"],"scope":row["scope"],
             "event_id":event_id,"status":"waiting_approval"}
            for row in candidates if row["last_fired"] is None
            or current - row["last_fired"] >= row["cooldown"]
        ]
        if dry_run:
            return matches
        with self.db:
            receipt = self.db.execute(
                "INSERT OR IGNORE INTO event_receipts(owner,event_id,recorded)"
                " VALUES(?,?,?)", (principal.user_id,event_id,current),
            )
            if receipt.rowcount == 0:
                return []
            for match in matches:
                self.db.execute(
                    "INSERT OR IGNORE INTO pending_actions(id,rule_id,event_id,owner,created)"
                    " VALUES(?,?,?,?,?)",
                    (uuid.uuid4().hex,match["rule_id"],event_id,
                     principal.user_id,current),
                )
                self.db.execute("UPDATE rules SET last_fired=? WHERE id=?",
                                (current,match["rule_id"]))
            # Avoid unbounded receipt table growth.
            self.db.execute(
                "DELETE FROM event_receipts WHERE recorded < ?", (current-30*86400,)
            )
        return matches

    def close(self) -> None:
        self.db.close()
