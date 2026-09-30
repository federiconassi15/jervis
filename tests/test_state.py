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
