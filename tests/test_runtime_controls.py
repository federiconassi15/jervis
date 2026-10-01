import time

from jervis.state import State


def test_auth_grant_is_atomic(tmp_path):
    state = State(tmp_path / "state.sqlite3")
    state.set_kv("auth.tui_grant", {"user_id": "u1", "issued_at": time.time()})
    grant = state.pop_kv("auth.tui_grant")
    assert grant["user_id"] == "u1"
    assert state.pop_kv("auth.tui_grant") is None
    state.close()


def test_recent_dialogue_is_chronological(tmp_path):
    state = State(tmp_path / "state.sqlite3")
    state.dialogue("unknown", "first")
    state.dialogue("jervis", "second")
    rows = state.recent_dialogue(10)
    assert [row["text"] for row in rows] == ["first", "second"]
    state.close()
