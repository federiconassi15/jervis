from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from threading import RLock
from typing import Any

STATE_SCHEMA_VERSION = 3

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
CREATE TABLE IF NOT EXISTS session_summaries(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  started_at REAL NOT NULL,
  ended_at REAL NOT NULL,
  topic TEXT NOT NULL DEFAULT '',
  summary TEXT NOT NULL,
  provenance TEXT NOT NULL DEFAULT 'runtime',
  created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_session_summaries_user
  ON session_summaries(user_id,ended_at DESC);
CREATE TABLE IF NOT EXISTS presence_history(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts REAL NOT NULL,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  transition TEXT NOT NULL,
  source TEXT NOT NULL,
  confidence REAL NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_presence_history_user
  ON presence_history(user_id,id DESC);
CREATE TABLE IF NOT EXISTS agent_runs(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
  agent TEXT NOT NULL,
  route TEXT NOT NULL,
  status TEXT NOT NULL,
  started_at REAL NOT NULL,
  ended_at REAL,
  detail TEXT NOT NULL DEFAULT '',
  cancel_requested INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_agent_runs_user
  ON agent_runs(user_id,id DESC);
CREATE TABLE IF NOT EXISTS agent_actions(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id INTEGER NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
  ts REAL NOT NULL,
  kind TEXT NOT NULL,
  name TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT '',
  detail TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_agent_actions_run
  ON agent_actions(run_id,id);
CREATE TABLE IF NOT EXISTS condition_watches(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
  key TEXT NOT NULL,
  kind TEXT NOT NULL,
  spec TEXT NOT NULL,
  message TEXT NOT NULL,
  reason TEXT NOT NULL DEFAULT '',
  priority INTEGER NOT NULL DEFAULT 0,
  created_at REAL NOT NULL,
  expires_at REAL,
  check_interval REAL NOT NULL DEFAULT 60,
  last_checked REAL,
  last_value TEXT NOT NULL DEFAULT '',
  active INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_condition_watches_active
  ON condition_watches(active,id);
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
        existed_before = path.exists()
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
        current_version = int(self._db.execute("PRAGMA user_version").fetchone()[0])
        if existed_before and current_version < STATE_SCHEMA_VERSION:
            try:
                from .paths import Paths
                from .snapshots import create_snapshot
                resolved = Paths.resolve()
                if path.resolve() == (resolved.data / "jervis.sqlite3").resolve():
                    create_snapshot("pre-db-migration", paths=resolved)
            except Exception:
                pass
        if current_version > STATE_SCHEMA_VERSION:
            raise RuntimeError(
                "database schema "
                + str(current_version)
                + " is newer than this Jervis build supports ("
                + str(STATE_SCHEMA_VERSION)
                + ")"
            )
        self._db.executescript(SCHEMA)
        if current_version < 2:
            memory_columns = {
                str(row["name"])
                for row in self._db.execute("PRAGMA table_info(memories)")
            }
            for name, declaration in (
                ("provenance", "TEXT NOT NULL DEFAULT 'explicit'"),
                ("importance", "REAL NOT NULL DEFAULT 0.5"),
                ("last_accessed", "REAL"),
                ("access_count", "INTEGER NOT NULL DEFAULT 0"),
            ):
                if name not in memory_columns:
                    self._db.execute(
                        "ALTER TABLE memories ADD COLUMN " + name + " " + declaration
                    )

            notification_columns = {
                str(row["name"])
                for row in self._db.execute("PRAGMA table_info(notifications)")
            }
            for name, declaration in (
                ("priority", "INTEGER NOT NULL DEFAULT 0"),
                ("expires_at", "REAL"),
                ("not_before", "REAL"),
                ("reason", "TEXT NOT NULL DEFAULT ''"),
                ("attempts", "INTEGER NOT NULL DEFAULT 0"),
                ("delivered_at", "REAL"),
            ):
                if name not in notification_columns:
                    self._db.execute(
                        "ALTER TABLE notifications ADD COLUMN " + name + " " + declaration
                    )

        if current_version < 3:
            agent_columns = {
                str(row["name"])
                for row in self._db.execute("PRAGMA table_info(agent_runs)")
            }
            if "cancel_requested" not in agent_columns:
                self._db.execute(
                    "ALTER TABLE agent_runs ADD COLUMN "
                    "cancel_requested INTEGER NOT NULL DEFAULT 0"
                )

        if current_version < STATE_SCHEMA_VERSION:
            self._db.execute("PRAGMA user_version=" + str(STATE_SCHEMA_VERSION))
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
        summary_limit: int = 3,
        query: str = "",
    ) -> dict[str, Any]:
        with self._lock:
            user = self._db.execute(
                "SELECT * FROM users WHERE id=?",
                (user_id,),
            ).fetchone()
            memory_candidates = (
                list(
                    self._db.execute(
                        "SELECT key,value,created_at,updated_at,provenance,importance,"
                        "last_accessed,access_count FROM memories "
                        "WHERE user_id=? ORDER BY updated_at DESC LIMIT ?",
                        (user_id, max(int(memory_limit) * 6, 24)),
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
            summaries = (
                list(
                    self._db.execute(
                        "SELECT started_at,ended_at,topic,summary,provenance "
                        "FROM session_summaries WHERE user_id=? "
                        "ORDER BY ended_at DESC LIMIT ?",
                        (user_id, max(0, int(summary_limit))),
                    )
                )
                if int(summary_limit) > 0
                else []
            )
            agent = self._db.execute(
                "SELECT value FROM kv WHERE key=?",
                ("brain.agent." + user_id,),
            ).fetchone()

        dialogue.reverse()
        summaries.reverse()

        terms = {
            token
            for token in "".join(
                char.lower() if char.isalnum() else " " for char in query
            ).split()
            if len(token) > 2
        }
        now = time.time()

        def memory_score(row) -> float:
            value_text = str(json.loads(row["value"])).lower()
            key_text = str(row["key"]).lower()
            lexical = sum(
                1.0 for term in terms if term in value_text or term in key_text
            )
            age_days = max(0.0, (now - float(row["updated_at"])) / 86400.0)
            recency = 1.0 / (1.0 + age_days / 30.0)
            importance = max(0.0, min(1.0, float(row["importance"])))
            access = min(1.0, float(row["access_count"]) / 8.0)
            return lexical * 3.0 + importance * 1.5 + recency + access * 0.5

        ranked = sorted(
            memory_candidates,
            key=memory_score,
            reverse=True,
        )[: max(0, int(memory_limit))]

        if ranked:
            keys = [str(row["key"]) for row in ranked]
            placeholders = ",".join("?" for _ in keys)
            with self._lock:
                self._db.execute(
                    "UPDATE memories SET last_accessed=?,access_count=access_count+1 "
                    "WHERE user_id=? AND key IN (" + placeholders + ")",
                    (now, user_id, *keys),
                )
                self._db.commit()

        return {
            "user": user,
            "memories": [
                {
                    "key": str(row["key"]),
                    "value": json.loads(row["value"]),
                    "created_at": float(row["created_at"]),
                    "updated_at": float(row["updated_at"]),
                    "provenance": str(row["provenance"]),
                    "importance": float(row["importance"]),
                    "score": memory_score(row),
                }
                for row in ranked
            ],
            "dialogue": dialogue,
            "summaries": [
                {
                    "started_at": float(row["started_at"]),
                    "ended_at": float(row["ended_at"]),
                    "topic": str(row["topic"]),
                    "summary": str(row["summary"]),
                    "provenance": str(row["provenance"]),
                }
                for row in summaries
            ],
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

    def remember(
        self,
        user_id: str,
        key: str,
        value: Any,
        *,
        provenance: str = "explicit",
        importance: float = 0.5,
    ) -> None:
        clean = key.strip()
        if not clean:
            raise ValueError("memory key cannot be empty")
        now = time.time()
        importance = max(0.0, min(1.0, float(importance)))
        with self._lock:
            self._db.execute(
                """
                INSERT INTO memories(
                  user_id,key,value,created_at,updated_at,provenance,importance
                )
                VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(user_id,key) DO UPDATE SET
                  value=excluded.value,
                  updated_at=excluded.updated_at,
                  provenance=excluded.provenance,
                  importance=excluded.importance
                """,
                (
                    user_id,
                    clean,
                    self._json(value),
                    now,
                    now,
                    str(provenance)[:120],
                    importance,
                ),
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
                    "SELECT key,value,created_at,updated_at,provenance,importance,"
                    "last_accessed,access_count FROM memories "
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
                "provenance": str(row["provenance"]),
                "importance": float(row["importance"]),
                "last_accessed": (
                    None if row["last_accessed"] is None else float(row["last_accessed"])
                ),
                "access_count": int(row["access_count"]),
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

    def save_session_summary(
        self,
        user_id: str,
        summary: str,
        *,
        started_at: float,
        ended_at: float | None = None,
        topic: str = "",
        provenance: str = "runtime",
    ) -> int:
        clean = summary.strip()
        if not clean:
            raise ValueError("session summary cannot be empty")
        end = time.time() if ended_at is None else float(ended_at)
        with self._lock:
            cursor = self._db.execute(
                "INSERT INTO session_summaries("
                "user_id,started_at,ended_at,topic,summary,provenance,created_at"
                ") VALUES(?,?,?,?,?,?,?)",
                (
                    user_id,
                    float(started_at),
                    end,
                    str(topic)[:240],
                    clean[:6000],
                    str(provenance)[:120],
                    time.time(),
                ),
            )
            self._db.commit()
            return int(cursor.lastrowid)

    def recent_session_summaries(
        self,
        user_id: str,
        limit: int = 5,
    ) -> list[sqlite3.Row]:
        with self._lock:
            rows = list(
                self._db.execute(
                    "SELECT id,started_at,ended_at,topic,summary,provenance "
                    "FROM session_summaries WHERE user_id=? "
                    "ORDER BY ended_at DESC LIMIT ?",
                    (user_id, max(1, int(limit))),
                )
            )
        rows.reverse()
        return rows

    def record_presence_transition(
        self,
        user_id: str,
        transition: str,
        source: str,
        confidence: float,
    ) -> None:
        with self._lock:
            self._db.execute(
                "INSERT INTO presence_history(ts,user_id,transition,source,confidence) "
                "VALUES(?,?,?,?,?)",
                (
                    time.time(),
                    user_id,
                    str(transition)[:40],
                    str(source)[:120],
                    float(confidence),
                ),
            )
            self._db.commit()

    def presence_history(self, user_id: str, limit: int = 20) -> list[sqlite3.Row]:
        with self._lock:
            rows = list(
                self._db.execute(
                    "SELECT ts,transition,source,confidence FROM presence_history "
                    "WHERE user_id=? ORDER BY id DESC LIMIT ?",
                    (user_id, max(1, int(limit))),
                )
            )
        rows.reverse()
        return rows

    def begin_agent_run(
        self,
        user_id: str | None,
        agent: str,
        route: str,
    ) -> int:
        with self._lock:
            cursor = self._db.execute(
                "INSERT INTO agent_runs(user_id,agent,route,status,started_at) "
                "VALUES(?,?,?,?,?)",
                (user_id, agent, route, "running", time.time()),
            )
            self._db.commit()
            return int(cursor.lastrowid)

    def finish_agent_run(
        self,
        run_id: int,
        status: str,
        detail: str = "",
    ) -> None:
        with self._lock:
            self._db.execute(
                "UPDATE agent_runs SET status=?,ended_at=?,detail=? WHERE id=?",
                (
                    str(status)[:40],
                    time.time(),
                    str(detail)[:1000],
                    int(run_id),
                ),
            )
            self._db.commit()

    def request_agent_cancel(self, run_id: int) -> bool:
        with self._lock:
            cursor = self._db.execute(
                "UPDATE agent_runs SET cancel_requested=1 "
                "WHERE id=? AND status='running'",
                (int(run_id),),
            )
            self._db.commit()
            if cursor.rowcount:
                self._insert_event_locked(
                    "agent_cancel_requested",
                    "run=" + str(int(run_id)),
                )
                self._db.commit()
            return bool(cursor.rowcount)

    def agent_cancel_requested(self, run_id: int) -> bool:
        with self._lock:
            row = self._db.execute(
                "SELECT cancel_requested FROM agent_runs WHERE id=?",
                (int(run_id),),
            ).fetchone()
        return bool(row and row["cancel_requested"])

    def add_agent_action(
        self,
        run_id: int,
        kind: str,
        name: str,
        *,
        status: str = "",
        detail: str = "",
    ) -> int:
        with self._lock:
            cursor = self._db.execute(
                "INSERT INTO agent_actions(run_id,ts,kind,name,status,detail) "
                "VALUES(?,?,?,?,?,?)",
                (
                    int(run_id),
                    time.time(),
                    str(kind)[:80],
                    str(name)[:240],
                    str(status)[:80],
                    str(detail)[:1000],
                ),
            )
            self._db.commit()
            return int(cursor.lastrowid)

    def agent_actions(self, run_id: int, limit: int = 100) -> list[sqlite3.Row]:
        with self._lock:
            return list(
                self._db.execute(
                    "SELECT id,ts,kind,name,status,detail FROM agent_actions "
                    "WHERE run_id=? ORDER BY id ASC LIMIT ?",
                    (int(run_id), max(1, int(limit))),
                )
            )

    def recent_agent_runs(
        self,
        user_id: str | None = None,
        limit: int = 20,
    ) -> list[sqlite3.Row]:
        with self._lock:
            if user_id is None:
                return list(
                    self._db.execute(
                        "SELECT * FROM agent_runs ORDER BY id DESC LIMIT ?",
                        (max(1, int(limit)),),
                    )
                )
            return list(
                self._db.execute(
                    "SELECT * FROM agent_runs WHERE user_id=? "
                    "ORDER BY id DESC LIMIT ?",
                    (user_id, max(1, int(limit))),
                )
            )

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

    def create_condition_watch(
        self,
        key: str,
        kind: str,
        spec: Any,
        message: str,
        user_id: str | None = None,
        *,
        reason: str = "",
        priority: int = 10,
        expires_at: float | None = None,
        check_interval: float = 60.0,
    ) -> int:
        with self._lock:
            cursor = self._db.execute(
                "INSERT INTO condition_watches("
                "user_id,key,kind,spec,message,reason,priority,created_at,"
                "expires_at,check_interval,last_checked,last_value,active"
                ") VALUES(?,?,?,?,?,?,?,?,?,?,NULL,'',1)",
                (
                    user_id,
                    str(key)[:240],
                    str(kind)[:80],
                    self._json(spec),
                    str(message)[:2000],
                    str(reason)[:500],
                    int(priority),
                    time.time(),
                    expires_at,
                    max(1.0, float(check_interval)),
                ),
            )
            self._db.commit()
            return int(cursor.lastrowid)

    def due_condition_watches(
        self,
        *,
        now: float | None = None,
        limit: int = 50,
    ) -> list[sqlite3.Row]:
        stamp = time.time() if now is None else float(now)
        with self._lock:
            return list(
                self._db.execute(
                    "SELECT * FROM condition_watches "
                    "WHERE active=1 "
                    "AND (expires_at IS NULL OR expires_at>?) "
                    "AND (last_checked IS NULL OR last_checked+check_interval<=?) "
                    "ORDER BY id ASC LIMIT ?",
                    (stamp, stamp, max(1, int(limit))),
                )
            )

    def condition_watches(
        self,
        user_id: str | None = None,
        *,
        active_only: bool = True,
        limit: int = 50,
    ) -> list[sqlite3.Row]:
        query = "SELECT * FROM condition_watches WHERE 1=1 "
        params: list[Any] = []
        if active_only:
            query += "AND active=1 "
        if user_id is not None:
            query += "AND (user_id IS NULL OR user_id=?) "
            params.append(user_id)
        query += "ORDER BY id DESC LIMIT ?"
        params.append(max(1, int(limit)))
        with self._lock:
            return list(self._db.execute(query, tuple(params)))

    def mark_condition_checked(
        self,
        watch_id: int,
        value: Any,
        *,
        now: float | None = None,
    ) -> None:
        stamp = time.time() if now is None else float(now)
        with self._lock:
            self._db.execute(
                "UPDATE condition_watches SET last_checked=?,last_value=? WHERE id=?",
                (stamp, self._json(value), int(watch_id)),
            )
            self._db.commit()

    def complete_condition_watch(self, watch_id: int) -> None:
        with self._lock:
            self._db.execute(
                "UPDATE condition_watches SET active=0 WHERE id=?",
                (int(watch_id),),
            )
            self._db.commit()

    def cancel_condition_watch(self, watch_id: int) -> bool:
        with self._lock:
            cursor = self._db.execute(
                "UPDATE condition_watches SET active=0 WHERE id=? AND active=1",
                (int(watch_id),),
            )
            self._db.commit()
            return bool(cursor.rowcount)

    def expire_condition_watches(self, now: float | None = None) -> int:
        stamp = time.time() if now is None else float(now)
        with self._lock:
            cursor = self._db.execute(
                "UPDATE condition_watches SET active=0 "
                "WHERE active=1 AND expires_at IS NOT NULL AND expires_at<=?",
                (stamp,),
            )
            self._db.commit()
            return int(cursor.rowcount)

    def notify(
        self,
        key: str,
        text: str,
        user_id: str | None = None,
        *,
        priority: int = 0,
        expires_at: float | None = None,
        not_before: float | None = None,
        reason: str = "",
    ) -> int:
        with self._lock:
            cursor = self._db.execute(
                "INSERT INTO notifications("
                "ts,key,text,user_id,delivered,priority,expires_at,not_before,reason,attempts"
                ") VALUES(?,?,?,?,0,?,?,?,?,0)",
                (
                    time.time(),
                    key,
                    str(text)[:2000],
                    user_id,
                    int(priority),
                    expires_at,
                    not_before,
                    str(reason)[:500],
                ),
            )
            self._db.commit()
            return int(cursor.lastrowid)

    def expire_notifications(self, now: float | None = None) -> int:
        stamp = time.time() if now is None else float(now)
        with self._lock:
            cursor = self._db.execute(
                "UPDATE notifications SET delivered=1,delivered_at=? "
                "WHERE delivered=0 AND expires_at IS NOT NULL AND expires_at<=?",
                (stamp, stamp),
            )
            self._db.commit()
            return int(cursor.rowcount)

    def next_notification(
        self,
        user_id: str | None = None,
        *,
        now: float | None = None,
    ):
        stamp = time.time() if now is None else float(now)
        with self._lock:
            base = (
                "SELECT id,key,text,user_id,priority,expires_at,not_before,reason,attempts "
                "FROM notifications WHERE delivered=0 "
                "AND (expires_at IS NULL OR expires_at>?) "
                "AND (not_before IS NULL OR not_before<=?) "
            )
            if user_id is None:
                return self._db.execute(
                    base + "ORDER BY priority DESC,id ASC LIMIT 1",
                    (stamp, stamp),
                ).fetchone()
            return self._db.execute(
                base
                + "AND (user_id IS NULL OR user_id=?) "
                + "ORDER BY priority DESC,id ASC LIMIT 1",
                (stamp, stamp, user_id),
            ).fetchone()

    def pending_notifications(
        self,
        user_id: str | None = None,
        limit: int = 50,
    ) -> list[sqlite3.Row]:
        with self._lock:
            if user_id is None:
                return list(
                    self._db.execute(
                        "SELECT id,ts,key,text,user_id,priority,expires_at,not_before,"
                        "reason,attempts FROM notifications WHERE delivered=0 "
                        "ORDER BY priority DESC,id ASC LIMIT ?",
                        (max(1, int(limit)),),
                    )
                )
            return list(
                self._db.execute(
                    "SELECT id,ts,key,text,user_id,priority,expires_at,not_before,"
                    "reason,attempts FROM notifications WHERE delivered=0 "
                    "AND (user_id IS NULL OR user_id=?) "
                    "ORDER BY priority DESC,id ASC LIMIT ?",
                    (user_id, max(1, int(limit))),
                )
            )

    def defer_notification(
        self,
        notification_id: int,
        until: float,
    ) -> None:
        with self._lock:
            self._db.execute(
                "UPDATE notifications SET not_before=?,attempts=attempts+1 WHERE id=?",
                (float(until), int(notification_id)),
            )
            self._db.commit()

    def cancel_notification(self, notification_id: int) -> bool:
        with self._lock:
            cursor = self._db.execute(
                "UPDATE notifications SET delivered=1,delivered_at=? "
                "WHERE id=? AND delivered=0",
                (time.time(), int(notification_id)),
            )
            self._db.commit()
            return bool(cursor.rowcount)

    def mark_notification(self, notification_id: int) -> None:
        with self._lock:
            self._db.execute(
                "UPDATE notifications SET delivered=1,delivered_at=? WHERE id=?",
                (time.time(), int(notification_id)),
            )
            self._db.commit()
