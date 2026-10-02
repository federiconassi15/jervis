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
