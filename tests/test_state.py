import sqlite3

from jervis.state import State


def test_users_embeddings_and_bounded_history(tmp_path):
    state = State(tmp_path / "state.sqlite3", max_dialogue=3, max_events=3)
    try:
        state.upsert_user("u1", "Alex", "sir", "owner")
        assert state.user_by_name("alex")["id"] == "u1"

        for index in range(5):
            state.add_embedding("u1", [1.0, float(index)], 0.5 + index / 10, 3)
        assert len(state.embeddings()["u1"]) == 3

        for index in range(5):
            state.dialogue("user", f"message-{index}", "u1")
            state.event("test", f"event-{index}")

        dialogue_count = state._db.execute("SELECT COUNT(*) FROM dialogue").fetchone()[0]
        event_count = state._db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        assert dialogue_count == 3
        assert event_count == 3
    finally:
        state.close()


def test_kv_roundtrip(tmp_path):
    state = State(tmp_path / "state.sqlite3")
    try:
        state.set_kv("example", {"value": 42})
        assert state.get_kv("example") == {"value": 42}
        assert state.get_kv("missing", "fallback") == "fallback"
    finally:
        state.close()


def test_per_user_memory_and_presence(tmp_path):
    state = State(tmp_path / "state.sqlite3")
    try:
        state.upsert_user("u1", "Alex", "sir", "owner")
        state.remember("u1", "coffee", {"order": "flat white"})
        assert state.memory("u1", "coffee") == {"order": "flat white"}
        assert state.memories("u1")[0]["key"] == "coffee"

        state.set_presence("u1", "voice", 0.91, True)
        present = state.presence(present_only=True)
        assert len(present) == 1
        assert present[0]["name"] == "Alex"

        state.forget_memory("u1", "coffee")
        assert state.memory("u1", "coffee") is None
    finally:
        state.close()


def test_context_snapshot_batches_user_memory_dialogue_and_agent(tmp_path):
    state = State(tmp_path / "state.sqlite3")
    try:
        state.upsert_user("u1", "Alex", "sir", "owner")
        state.remember("u1", "music", "synthwave")
        state.dialogue("Alex", "hello", "u1")
        state.set_kv("brain.agent.u1", "ops")

        snapshot = state.context_snapshot("u1")
        assert snapshot["user"]["name"] == "Alex"
        assert snapshot["memories"][0]["value"] == "synthwave"
        assert snapshot["dialogue"][0]["text"] == "hello"
        assert snapshot["agent"] == "ops"
    finally:
        state.close()


def test_context_snapshot_can_skip_dialogue(tmp_path):
    state = State(tmp_path / "state.sqlite3")
    try:
        state.upsert_user("u1", "Alex", "sir", "owner")
        state.remember("u1", "fact", "keep me")
        state.dialogue("Alex", "do not replay me", "u1")

        snapshot = state.context_snapshot(
            "u1",
            memory_limit=6,
            dialogue_limit=0,
        )
        assert snapshot["memories"][0]["value"] == "keep me"
        assert snapshot["dialogue"] == []
    finally:
        state.close()


def test_metrics_are_bounded_and_queryable(tmp_path):
    state = State(tmp_path / "state.sqlite3", max_metrics=100)
    try:
        for index in range(240):
            state.metric("brain_ms", float(index), detail="local")
        rows = state.recent_metrics("brain_ms", 200)
        assert len(rows) <= 110
        assert rows[-1]["value"] == 239.0
        assert rows[-1]["unit"] == "ms"
    finally:
        state.close()


def test_schema_2_database_migrates_in_place_without_losing_state(tmp_path):
    path = tmp_path / "state.sqlite3"
    db = sqlite3.connect(path)
    try:
        db.executescript(
            """
            PRAGMA user_version=2;
            CREATE TABLE users(
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL UNIQUE COLLATE NOCASE,
              honorific TEXT,
              role TEXT NOT NULL DEFAULT 'known',
              created_at REAL NOT NULL,
              last_seen REAL
            );
            CREATE TABLE memories(
              user_id TEXT NOT NULL,
              key TEXT NOT NULL,
              value TEXT NOT NULL,
              created_at REAL NOT NULL,
              updated_at REAL NOT NULL,
              provenance TEXT NOT NULL DEFAULT 'explicit',
              importance REAL NOT NULL DEFAULT 0.5,
              last_accessed REAL,
              access_count INTEGER NOT NULL DEFAULT 0,
              PRIMARY KEY(user_id,key)
            );
            CREATE TABLE notifications(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              ts REAL NOT NULL,
              key TEXT NOT NULL,
              text TEXT NOT NULL,
              user_id TEXT,
              delivered INTEGER NOT NULL DEFAULT 0,
              priority INTEGER NOT NULL DEFAULT 0,
              expires_at REAL,
              not_before REAL,
              reason TEXT NOT NULL DEFAULT '',
              attempts INTEGER NOT NULL DEFAULT 0,
              delivered_at REAL
            );
            CREATE TABLE agent_runs(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id TEXT,
              agent TEXT NOT NULL,
              route TEXT NOT NULL,
              status TEXT NOT NULL,
              started_at REAL NOT NULL,
              ended_at REAL,
              detail TEXT NOT NULL DEFAULT ''
            );
            """
        )
        db.execute(
            "INSERT INTO users(id,name,honorific,role,created_at,last_seen) "
            "VALUES('u1','Alex','sir','owner',1,1)"
        )
        db.execute(
            "INSERT INTO memories("
            "user_id,key,value,created_at,updated_at,provenance,importance,"
            "last_accessed,access_count"
            ") VALUES('u1','music','\"synthwave\"',1,2,'voice:explicit',0.8,NULL,0)"
        )
        db.execute(
            "INSERT INTO agent_runs("
            "user_id,agent,route,status,started_at,detail"
            ") VALUES('u1','main','openclaw:deep','running',3,'')"
        )
        db.commit()
    finally:
        db.close()

    state = State(path)
    try:
        assert state._db.execute("PRAGMA user_version").fetchone()[0] == 3
        assert state.memory("u1", "music") == "synthwave"

        agent_columns = {
            row["name"]
            for row in state._db.execute("PRAGMA table_info(agent_runs)")
        }
        assert "cancel_requested" in agent_columns
        tables = {
            row[0]
            for row in state._db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert "agent_actions" in tables

        run = state.recent_agent_runs("u1", 1)[0]
        assert run["status"] == "running"
        assert state.request_agent_cancel(int(run["id"])) is True
        assert state.agent_cancel_requested(int(run["id"])) is True
    finally:
        state.close()
