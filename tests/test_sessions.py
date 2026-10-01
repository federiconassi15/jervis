import jervis.sessions as sessions_module

from jervis.sessions import SessionManager
from jervis.state import State


def test_trusted_session(tmp_path):
    state = State(tmp_path / "state.sqlite3")
    state.upsert_user("u1", "Alex")
    manager = SessionManager(state, 3600, 600)
    session = manager.create("u1", 0.9, "test")
    assert manager.active() is session
    assert manager.refresh() is session
    manager.clear()
    assert manager.active() is None
    state.close()


def test_refresh_rolls_expiry_forward(monkeypatch, tmp_path):
    state = State(tmp_path / "state.sqlite3")
    state.upsert_user("u1", "Alex")

    now = [100.0]
    monkeypatch.setattr(
        sessions_module.time,
        "time",
        lambda: now[0],
    )

    manager = SessionManager(state, lifetime=10, inactivity=8)
    session = manager.create("u1", 0.8, "test")
    assert session.expires_at == 110.0

    now[0] = 105.0
    refreshed = manager.refresh(0.9)
    assert refreshed is session
    assert session.refreshed_at == 105.0
    assert session.expires_at == 115.0
    assert session.confidence == 0.9

    state.close()
