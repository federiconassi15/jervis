from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from threading import RLock
from typing import Any

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA foreign_keys=ON;
PRAGMA temp_store=MEMORY;
PRAGMA busy_timeout=5000;
PRAGMA wal_autocheckpoint=1000;
CREATE TABLE IF NOT EXISTS users(
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE COLLATE NOCASE,
  honorific TEXT CHECK(honorific IN ('sir','maam') OR honorific IS NULL),
  role TEXT NOT NULL DEFAULT 'known',
  created_at REAL NOT NULL,
  last_seen REAL
);
CREATE TABLE IF NOT EXISTS speaker_embeddings(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  embedding TEXT NOT NULL,
  quality REAL NOT NULL DEFAULT 1.0,
  created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_embeddings_user
  ON speaker_embeddings(user_id,quality DESC,created_at DESC);
CREATE TABLE IF NOT EXISTS dialogue(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts REAL NOT NULL,
  user_id TEXT,
  role TEXT NOT NULL,
  text TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_dialogue_ts ON dialogue(ts DESC);
CREATE INDEX IF NOT EXISTS idx_dialogue_user_id ON dialogue(user_id,id DESC);
CREATE TABLE IF NOT EXISTS events(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts REAL NOT NULL,
  kind TEXT NOT NULL,
  detail TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts DESC);
CREATE TABLE IF NOT EXISTS memories(
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  key TEXT NOT NULL,
  value TEXT NOT NULL,
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL,
  PRIMARY KEY(user_id,key)
);
CREATE INDEX IF NOT EXISTS idx_memories_user_updated
  ON memories(user_id,updated_at DESC);
CREATE TABLE IF NOT EXISTS presence(
  user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  source TEXT NOT NULL,
  confidence REAL NOT NULL DEFAULT 0,
  present INTEGER NOT NULL DEFAULT 1,
  seen_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_presence_seen ON presence(present,seen_at DESC);
CREATE TABLE IF NOT EXISTS notifications(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts REAL NOT NULL,
  key TEXT NOT NULL,
  text TEXT NOT NULL,
  user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
  delivered INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_notifications_delivery
  ON notifications(delivered,user_id,id);
CREATE TABLE IF NOT EXISTS metrics(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts REAL NOT NULL,
  name TEXT NOT NULL,
  value REAL NOT NULL,
  unit TEXT NOT NULL,
  detail TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_metrics_name_id ON metrics(name,id DESC);
CREATE TABLE IF NOT EXISTS kv(
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
"""


class State:
    PRUNE_EVERY = 64
    METRIC_PRUNE_EVERY = 128

    def __init__(
        self,
        path: Path,
        max_dialogue: int = 2000,
        max_events: int = 5000,
        max_metrics: int = 5000,
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.max_dialogue = max(1, int(max_dialogue))
        self.max_events = max(1, int(max_events))
        self.max_metrics = max(100, int(max_metrics))
        self._lock = RLock()
        self._db = sqlite3.connect(
            path,
            check_same_thread=False,
            timeout=5.0,
            isolation_level="DEFERRED",
        )
        self._db.row_factory = sqlite3.Row
        self._db.executescript(SCHEMA)
        self._db.commit()
        self._events_since_prune = 0
        self._dialogue_since_prune = 0
        self._metrics_since_prune = 0
        self._embedding_cache: dict[str, list[list[float]]] | None = None

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, separators=(",", ":"), ensure_ascii=False)

    def close(self) -> None:
        with self._lock:
            try:
                self._prune_events(force=True)
                self._prune_dialogue(force=True)
                self._prune_metrics(force=True)
                self._db.execute("PRAGMA optimize")
                self._db.commit()
            finally:
                self._db.close()

    def _prune_events(self, *, force: bool = False) -> None:
        threshold = min(self.PRUNE_EVERY, max(1, self.max_events // 4))
        if not force and self._events_since_prune < threshold:
            return
        self._db.execute(
            "DELETE FROM events WHERE id <= COALESCE(("
            "SELECT id FROM events ORDER BY id DESC LIMIT 1 OFFSET ?"
            "),0)",
            (self.max_events,),
        )
        self._events_since_prune = 0

    def _prune_dialogue(self, *, force: bool = False) -> None:
        threshold = min(self.PRUNE_EVERY, max(1, self.max_dialogue // 4))
        if not force and self._dialogue_since_prune < threshold:
            return
        self._db.execute(
            "DELETE FROM dialogue WHERE id <= COALESCE(("
            "SELECT id FROM dialogue ORDER BY id DESC LIMIT 1 OFFSET ?"
            "),0)",
            (self.max_dialogue,),
        )
        self._dialogue_since_prune = 0

    def _prune_metrics(self, *, force: bool = False) -> None:
        threshold = min(
            self.METRIC_PRUNE_EVERY,
            max(1, self.max_metrics // 10),
        )
        if not force and self._metrics_since_prune < threshold:
            return
        self._db.execute(
            "DELETE FROM metrics WHERE id <= COALESCE(("
            "SELECT id FROM metrics ORDER BY id DESC LIMIT 1 OFFSET ?"
            "),0)",
            (self.max_metrics,),
        )
        self._metrics_since_prune = 0

    def metric(
        self,
        name: str,
        value: float,
        unit: str = "ms",
        detail: str = "",
    ) -> None:
        with self._lock:
            self._db.execute(
                "INSERT INTO metrics(ts,name,value,unit,detail) VALUES(?,?,?,?,?)",
                (
                    time.time(),
                    str(name)[:120],
                    float(value),
                    str(unit)[:32],
                    str(detail)[:500],
                ),
            )
            self._metrics_since_prune += 1
            self._prune_metrics()
            # Deliberately do not commit here. Runtime telemetry piggybacks on
            # the next normal state commit instead of adding an fsync to the
            # latency path. close() also commits any remaining samples.

    def recent_metrics(
        self,
        name: str | None = None,
        limit: int = 100,
    ) -> list[sqlite3.Row]:
        with self._lock:
            if name is None:
                rows = list(
                    self._db.execute(
                        "SELECT ts,name,value,unit,detail FROM metrics "
                        "ORDER BY id DESC LIMIT ?",
                        (max(1, int(limit)),),
                    )
                )
            else:
                rows = list(
                    self._db.execute(
                        "SELECT ts,name,value,unit,detail FROM metrics "
                        "WHERE name=? ORDER BY id DESC LIMIT ?",
                        (name, max(1, int(limit))),
                    )
                )
        rows.reverse()
        return rows

    def _insert_event_locked(self, kind: str, detail: str = "") -> None:
        self._db.execute(
            "INSERT INTO events(ts,kind,detail) VALUES(?,?,?)",
            (time.time(), kind, str(detail)[:4000]),
        )
        self._events_since_prune += 1
        self._prune_events()

    def event(self, kind: str, detail: str = "") -> None:
        with self._lock:
            self._insert_event_locked(kind, detail)
            self._db.commit()

    def recent_events(self, limit: int = 30) -> list[sqlite3.Row]:
        with self._lock:
            rows = list(
                self._db.execute(
                    "SELECT ts,kind,detail FROM events ORDER BY id DESC LIMIT ?",
                    (max(1, int(limit)),),
                )
            )
        rows.reverse()
        return rows

    def dialogue(self, role: str, text: str, user_id: str | None = None) -> None:
        with self._lock:
            self._db.execute(
                "INSERT INTO dialogue(ts,user_id,role,text) VALUES(?,?,?,?)",
                (time.time(), user_id, role, str(text)[:12000]),
            )
            self._dialogue_since_prune += 1
            self._prune_dialogue()
            self._db.commit()

    def recent_dialogue(self, limit: int = 30) -> list[sqlite3.Row]:
        with self._lock:
            rows = list(
                self._db.execute(
                    "SELECT ts,user_id,role,text FROM dialogue ORDER BY id DESC LIMIT ?",
                    (max(1, int(limit)),),
                )
            )
        rows.reverse()
        return rows

    def recent_user_dialogue(
        self,
        user_id: str,
        limit: int = 10,
    ) -> list[sqlite3.Row]:
        with self._lock:
            rows = list(
                self._db.execute(
                    "SELECT ts,user_id,role,text FROM dialogue "
                    "WHERE user_id=? ORDER BY id DESC LIMIT ?",
                    (user_id, max(1, int(limit))),
                )
            )
        rows.reverse()
        return rows

    def context_snapshot(
        self,
        user_id: str,
        *,
        memory_limit: int = 12,
        dialogue_limit: int = 8,
    ) -> dict[str, Any]:
        with self._lock:
            user = self._db.execute(
                "SELECT * FROM users WHERE id=?",
                (user_id,),
            ).fetchone()
            memories = (
                list(
                    self._db.execute(
                        "SELECT key,value,created_at,updated_at FROM memories "
                        "WHERE user_id=? ORDER BY updated_at DESC LIMIT ?",
                        (user_id, int(memory_limit)),
                    )
                )
                if int(memory_limit) > 0
                else []
            )
            dialogue = (
                list(
                    self._db.execute(
                        "SELECT ts,user_id,role,text FROM dialogue "
                        "WHERE user_id=? ORDER BY id DESC LIMIT ?",
                        (user_id, int(dialogue_limit)),
                    )
                )
                if int(dialogue_limit) > 0
                else []
            )
            agent = self._db.execute(
                "SELECT value FROM kv WHERE key=?",
                ("brain.agent." + user_id,),
            ).fetchone()

        dialogue.reverse()
        return {
            "user": user,
            "memories": [
                {
                    "key": str(row["key"]),
                    "value": json.loads(row["value"]),
                    "created_at": float(row["created_at"]),
                    "updated_at": float(row["updated_at"]),
                }
                for row in memories
            ],
            "dialogue": dialogue,
            "agent": None if agent is None else json.loads(agent["value"]),
        }

    def set_kv(self, key: str, value: Any) -> None:
        encoded = self._json(value)
        with self._lock:
            current = self._db.execute(
                "SELECT value FROM kv WHERE key=?",
                (key,),
            ).fetchone()
            if current is not None and str(current["value"]) == encoded:
                return
            self._db.execute(
                "INSERT INTO kv(key,value) VALUES(?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, encoded),
            )
            self._db.commit()

    def get_kv(self, key: str, default: Any = None) -> Any:
        with self._lock:
            row = self._db.execute(
                "SELECT value FROM kv WHERE key=?",
                (key,),
            ).fetchone()
        return default if row is None else json.loads(row["value"])

    def delete_kv(self, key: str) -> None:
        with self._lock:
            self._db.execute("DELETE FROM kv WHERE key=?", (key,))
            self._db.commit()

    def pop_kv(self, key: str, default: Any = None) -> Any:
        with self._lock:
            row = self._db.execute(
                "SELECT value FROM kv WHERE key=?",
                (key,),
            ).fetchone()
            if row is None:
                return default
            self._db.execute("DELETE FROM kv WHERE key=?", (key,))
            self._db.commit()
        return json.loads(row["value"])

    def user(self, user_id: str):
        with self._lock:
            return self._db.execute(
                "SELECT * FROM users WHERE id=?",
                (user_id,),
            ).fetchone()

    def user_by_name(self, name: str):
        with self._lock:
            return self._db.execute(
                "SELECT * FROM users WHERE name=? COLLATE NOCASE",
                (name,),
            ).fetchone()

    def users(self) -> list[sqlite3.Row]:
        with self._lock:
            return list(self._db.execute("SELECT * FROM users ORDER BY name"))

    def upsert_user(
        self,
        user_id: str,
        name: str,
        honorific: str | None = None,
        role: str = "known",
    ) -> None:
        if honorific not in {None, "sir", "maam"}:
            raise ValueError("invalid honorific")
        now = time.time()
        with self._lock:
            self._db.execute(
                """
                INSERT INTO users(id,name,honorific,role,created_at,last_seen)
                VALUES(?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                  name=excluded.name,
                  honorific=COALESCE(excluded.honorific,users.honorific),
                  role=excluded.role,
                  last_seen=excluded.last_seen
                """,
                (user_id, name.strip(), honorific, role, now, now),
            )
            self._db.commit()

    def touch_user(self, user_id: str, *, now: float | None = None) -> None:
        stamp = time.time() if now is None else float(now)
        with self._lock:
            self._db.execute(
                "UPDATE users SET last_seen=? "
                "WHERE id=? AND (last_seen IS NULL OR last_seen < ?)",
                (stamp, user_id, stamp - 5.0),
            )
            self._db.commit()

    def add_embedding(
        self,
        user_id: str,
        embedding: list[float],
        quality: float,
        limit: int,
    ) -> None:
        with self._lock:
            self._db.execute(
                "INSERT INTO speaker_embeddings(user_id,embedding,quality,created_at) "
                "VALUES(?,?,?,?)",
                (user_id, self._json(embedding), float(quality), time.time()),
            )
            self._db.execute(
                "DELETE FROM speaker_embeddings WHERE user_id=? AND id NOT IN "
                "(SELECT id FROM speaker_embeddings WHERE user_id=? "
                "ORDER BY quality DESC,created_at DESC LIMIT ?)",
                (user_id, user_id, int(limit)),
            )
            self._db.commit()
            self._embedding_cache = None

    def embeddings(self) -> dict[str, list[list[float]]]:
        with self._lock:
            if self._embedding_cache is None:
                rows = list(
                    self._db.execute(
                        "SELECT user_id,embedding FROM speaker_embeddings "
                        "ORDER BY user_id,quality DESC"
                    )
                )
                cache: dict[str, list[list[float]]] = {}
                for row in rows:
                    cache.setdefault(str(row["user_id"]), []).append(
                        json.loads(row["embedding"])
                    )
                self._embedding_cache = cache
            return {
                user_id: list(vectors)
                for user_id, vectors in self._embedding_cache.items()
            }

    def remember(self, user_id: str, key: str, value: Any) -> None:
        clean = key.strip()
        if not clean:
            raise ValueError("memory key cannot be empty")
        now = time.time()
        with self._lock:
            self._db.execute(
                """
                INSERT INTO memories(user_id,key,value,created_at,updated_at)
                VALUES(?,?,?,?,?)
                ON CONFLICT(user_id,key) DO UPDATE SET
                  value=excluded.value,
                  updated_at=excluded.updated_at
                """,
                (user_id, clean, self._json(value), now, now),
            )
            self._db.commit()

    def memory(self, user_id: str, key: str, default: Any = None) -> Any:
        with self._lock:
            row = self._db.execute(
                "SELECT value FROM memories WHERE user_id=? AND key=?",
                (user_id, key.strip()),
            ).fetchone()
        return default if row is None else json.loads(row["value"])

    def memories(self, user_id: str, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            rows = list(
                self._db.execute(
                    "SELECT key,value,created_at,updated_at FROM memories "
                    "WHERE user_id=? ORDER BY updated_at DESC LIMIT ?",
                    (user_id, max(1, int(limit))),
                )
            )
        return [
            {
                "key": str(row["key"]),
                "value": json.loads(row["value"]),
                "created_at": float(row["created_at"]),
                "updated_at": float(row["updated_at"]),
            }
            for row in rows
        ]

    def forget_memory(self, user_id: str, key: str) -> None:
        with self._lock:
            self._db.execute(
                "DELETE FROM memories WHERE user_id=? AND key=?",
                (user_id, key.strip()),
            )
            self._db.commit()

    def clear_memories(self, user_id: str) -> None:
        with self._lock:
            self._db.execute("DELETE FROM memories WHERE user_id=?", (user_id,))
            self._db.commit()

    def set_presence(
        self,
        user_id: str,
        source: str,
        confidence: float,
        present: bool = True,
    ) -> bool:
        now = time.time()
        with self._lock:
            previous = self._db.execute(
                "SELECT present FROM presence WHERE user_id=?",
                (user_id,),
            ).fetchone()
            was_present = bool(previous and previous["present"])
            self._db.execute(
                """
                INSERT INTO presence(user_id,source,confidence,present,seen_at)
                VALUES(?,?,?,?,?)
                ON CONFLICT(user_id) DO UPDATE SET
                  source=excluded.source,
                  confidence=excluded.confidence,
                  present=excluded.present,
                  seen_at=excluded.seen_at
                """,
                (user_id, source, float(confidence), 1 if present else 0, now),
            )
            self._db.execute(
                "UPDATE users SET last_seen=? "
                "WHERE id=? AND (last_seen IS NULL OR last_seen < ?)",
                (now, user_id, now - 5.0),
            )
            self._db.commit()
            return was_present

    def presence(self, present_only: bool = False) -> list[sqlite3.Row]:
        query = (
            "SELECT p.user_id,u.name,p.source,p.confidence,p.present,p.seen_at "
            "FROM presence p JOIN users u ON u.id=p.user_id "
        )
        if present_only:
            query += "WHERE p.present=1 "
        query += "ORDER BY p.seen_at DESC"
        with self._lock:
            return list(self._db.execute(query))

    def notify(self, key: str, text: str, user_id: str | None = None) -> int:
        with self._lock:
            cursor = self._db.execute(
                "INSERT INTO notifications(ts,key,text,user_id,delivered) "
                "VALUES(?,?,?,?,0)",
                (time.time(), key, str(text)[:2000], user_id),
            )
            self._db.commit()
            return int(cursor.lastrowid)

    def next_notification(self, user_id: str | None = None):
        with self._lock:
            if user_id is None:
                return self._db.execute(
                    "SELECT id,key,text,user_id FROM notifications "
                    "WHERE delivered=0 ORDER BY id LIMIT 1"
                ).fetchone()
            return self._db.execute(
                "SELECT id,key,text,user_id FROM notifications "
                "WHERE delivered=0 AND (user_id IS NULL OR user_id=?) "
                "ORDER BY id LIMIT 1",
                (user_id,),
            ).fetchone()

    def mark_notification(self, notification_id: int) -> None:
        with self._lock:
            self._db.execute(
                "UPDATE notifications SET delivered=1 WHERE id=?",
                (int(notification_id),),
            )
            self._db.commit()
