import time

from jervis.sessions import SessionManager
from jervis.state import State


def test_trusted_session_lifecycle(tmp_path):
    state = State(tmp_path / "state.sqlite3")
    try:
        state.upsert_user("u1", "Alex")
        manager = SessionManager(state, 3600, 600)
        session = manager.create("u1", 0.9, "test")
        assert manager.active() is session
        assert manager.refresh(0.95).confidence == 0.95
        manager.clear()
        assert manager.active() is None
    finally:
        state.close()


def test_inactive_session_expires(tmp_path):
    state = State(tmp_path / "state.sqlite3")
    try:
        state.upsert_user("u1", "Alex")
        manager = SessionManager(state, 3600, 1)
        session = manager.create("u1", 0.9, "test")
        session.refreshed_at = time.time() - 2
        assert manager.active() is None
    finally:
        state.close()
