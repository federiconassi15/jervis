from __future__ import annotations

import sqlite3
import time

from types import SimpleNamespace

from jervis.agents import agent_capabilities
from jervis.presence import PresenceManager
from jervis.proactive import ProactiveEngine
from jervis.router import BrainRouter
from jervis.state import STATE_SCHEMA_VERSION, State


def test_state_schema_2_adds_continuity_tables_and_memory_metadata(tmp_path):
    path = tmp_path / "state.sqlite3"
    state = State(path)
    try:
        version = state._db.execute("PRAGMA user_version").fetchone()[0]
        assert version == STATE_SCHEMA_VERSION == 3

        tables = {
            row[0]
            for row in state._db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert {
            "session_summaries",
            "presence_history",
            "agent_runs",
            "agent_actions",
        } <= tables

        columns = {
            row["name"] for row in state._db.execute("PRAGMA table_info(memories)")
        }
        assert {"provenance", "importance", "last_accessed", "access_count"} <= columns
    finally:
        state.close()


def test_context_ranks_relevant_memory_and_tracks_provenance(tmp_path):
    state = State(tmp_path / "state.sqlite3")
    try:
        state.upsert_user("u1", "Alex", "sir", "owner")
        state.remember(
            "u1",
            "music",
            "likes System of a Down",
            provenance="voice:explicit",
            importance=0.8,
        )
        state.remember(
            "u1",
            "breakfast",
            "usually has cereal",
            provenance="voice:explicit",
            importance=0.8,
        )

        snapshot = state.context_snapshot(
            "u1",
            memory_limit=2,
            query="what music do I like?",
        )
        assert snapshot["memories"][0]["key"] == "music"
        assert snapshot["memories"][0]["provenance"] == "voice:explicit"
        assert state.memories("u1")[0]["access_count"] >= 0
    finally:
        state.close()


def test_session_summary_roundtrip(tmp_path):
    state = State(tmp_path / "state.sqlite3")
    try:
        state.upsert_user("u1", "Alex", "sir", "owner")
        state.save_session_summary(
            "u1",
            "Discussed the home server and audio setup.",
            started_at=10.0,
            ended_at=20.0,
            topic="home server",
        )
        snapshot = state.context_snapshot("u1", summary_limit=3)
        assert snapshot["summaries"][0]["topic"] == "home server"
        assert "audio setup" in snapshot["summaries"][0]["summary"]
    finally:
        state.close()


def test_presence_distinguishes_enter_return_and_handoff(tmp_path):
    state = State(tmp_path / "state.sqlite3")
    try:
        state.upsert_user("u1", "Alex", "sir", "owner")
        state.upsert_user("u2", "Sam", None, "known")
        presence = PresenceManager(
            state,
            timeout_seconds=30,
            return_window_seconds=300,
        )

        presence.seen("u1", "voice", 0.9)
        presence.seen("u2", "voice", 0.85)
        assert presence.active_user() == "u2"

        presence.left("u1")
        presence.seen("u1", "voice", 0.92)
        transitions = [
            str(row["transition"])
            for row in state.presence_history("u1")
        ]
        assert transitions[0] == "entered"
        assert "left" in transitions
        assert transitions[-1] == "returned"

        events = [str(row["kind"]) for row in state.recent_events(20)]
        assert "presence_handoff" in events
    finally:
        state.close()


def test_proactive_queue_prioritizes_and_expires(tmp_path):
    state = State(tmp_path / "state.sqlite3")
    spoken = []
    try:
        state.upsert_user("u1", "Alex", "sir", "owner")
        state.set_presence("u1", "voice", 1.0, True)
        state.set_kv("presence.active_user", "u1")

        engine = ProactiveEngine(
            state,
            {
                "enabled": True,
                "quiet_hours_start": "03:00",
                "quiet_hours_end": "03:01",
            },
            spoken.append,
        )
        now = time.time()
        state.notify(
            "expired",
            "do not say this",
            "u1",
            priority=99,
            expires_at=now - 1,
        )
        state.notify("low", "low priority", "u1", priority=1)
        state.notify(
            "high",
            "high priority",
            "u1",
            priority=10,
            reason="important test",
        )

        assert engine.tick() is True
        assert spoken == ["high priority"]
        assert state.next_notification("u1")["key"] == "low"
    finally:
        state.close()


def test_agent_run_history(tmp_path):
    state = State(tmp_path / "state.sqlite3")
    try:
        state.upsert_user("u1", "Alex", "sir", "owner")
        run_id = state.begin_agent_run("u1", "main", "openclaw:fast")
        state.finish_agent_run(run_id, "completed", "")
        row = state.recent_agent_runs("u1", 1)[0]
        assert row["agent"] == "main"
        assert row["status"] == "completed"
        assert row["ended_at"] is not None
    finally:
        state.close()


class _FakeBrain:
    agent = "main"


def _router(state, tmp_path):
    data = tmp_path / "data"
    data.mkdir(exist_ok=True)
    return BrainRouter(
        state,
        SimpleNamespace(data=data, root=tmp_path),
        _FakeBrain(),
        {
            "brain": {},
            "continuity": {},
            "proactive": {"default_ttl_seconds": 86400},
        },
    )


def test_local_relative_reminder_is_queued_for_later(tmp_path):
    state = State(tmp_path / "state.sqlite3")
    try:
        state.upsert_user("u1", "Alex", "sir", "owner")
        router = _router(state, tmp_path)
        before = time.time()
        reply = router._local(
            "remind me in 20 minutes to check the printer",
            "u1",
        )
        assert "20 minutes" in str(reply)
        rows = state.pending_notifications("u1")
        assert len(rows) == 1
        assert rows[0]["text"] == "Reminder: check the printer"
        assert float(rows[0]["not_before"]) >= before + 1190
        assert rows[0]["reason"] == "You asked me to remind you."
    finally:
        state.close()


def test_busy_window_suppresses_proactive_delivery(tmp_path):
    state = State(tmp_path / "state.sqlite3")
    spoken = []
    try:
        state.upsert_user("u1", "Alex", "sir", "owner")
        state.set_presence("u1", "voice", 1.0, True)
        state.set_kv("presence.active_user", "u1")
        router = _router(state, tmp_path)
        reply = router._local(
            "don't interrupt me for 30 minutes",
            "u1",
        )
        assert "won't proactively interrupt" in str(reply)

        state.notify(
            "queued",
            "This should wait.",
            "u1",
            priority=20,
        )
        engine = ProactiveEngine(
            state,
            {
                "enabled": True,
                "quiet_hours_start": "03:00",
                "quiet_hours_end": "03:01",
            },
            spoken.append,
        )
        assert engine.tick() is False
        assert spoken == []
        assert state.pending_notifications("u1")[0]["key"] == "queued"
    finally:
        state.close()


def test_proactive_reason_can_be_explained(tmp_path):
    state = State(tmp_path / "state.sqlite3")
    spoken = []
    try:
        state.upsert_user("u1", "Alex", "sir", "owner")
        state.set_presence("u1", "voice", 1.0, True)
        state.set_kv("presence.active_user", "u1")
        state.notify(
            "printer",
            "The printer is ready.",
            "u1",
            priority=5,
            reason="You asked me to tell you when the printer was ready.",
        )
        engine = ProactiveEngine(
            state,
            {
                "enabled": True,
                "quiet_hours_start": "03:00",
                "quiet_hours_end": "03:01",
            },
            spoken.append,
        )
        assert engine.tick() is True

        router = _router(state, tmp_path)
        explanation = router._local("why did you tell me that", "u1")
        assert "printer was ready" in str(explanation)
    finally:
        state.close()


def test_agent_capability_metadata_is_schema_tolerant():
    meta = agent_capabilities(
        {
            "name": "ops",
            "capabilities": {
                "browser": True,
                "filesystem": True,
                "cancel": False,
            },
            "tools": [
                {"name": "shell"},
                "search",
            ],
        }
    )
    assert meta["name"] == "ops"
    assert meta["capabilities"] == ["browser", "filesystem"]
    assert meta["tools"] == ["search", "shell"]
    assert meta["cancel_supported"] is False

    cancellable = agent_capabilities(
        {
            "id": "future-agent",
            "capabilities": ["search", "cancellable"],
        }
    )
    assert cancellable["name"] == "future-agent"
    assert cancellable["cancel_supported"] is True


def test_agent_run_cancellation_and_action_timeline(tmp_path):
    state = State(tmp_path / "state.sqlite3")
    try:
        state.upsert_user("u1", "Alex", "sir", "owner")
        run_id = state.begin_agent_run("u1", "main", "openclaw:deep")
        assert state.agent_cancel_requested(run_id) is False
        assert state.request_agent_cancel(run_id) is True
        assert state.agent_cancel_requested(run_id) is True

        state.add_agent_action(
            run_id,
            "tool_call",
            "search",
            status="completed",
            detail="query complete",
        )
        actions = state.agent_actions(run_id)
        assert len(actions) == 1
        assert actions[0]["name"] == "search"
        assert actions[0]["status"] == "completed"

        state.finish_agent_run(run_id, "cancelled", "user requested cancellation")
        row = state.recent_agent_runs("u1", 1)[0]
        assert row["status"] == "cancelled"
    finally:
        state.close()


def test_openclaw_action_extraction_is_tolerant():
    from jervis.brain.openclaw import _response_actions

    actions = _response_actions(
        {
            "output": [
                {
                    "type": "tool_call",
                    "name": "browser.search",
                    "status": "completed",
                },
                {
                    "type": "message",
                    "content": [{"text": "done"}],
                },
            ]
        }
    )
    assert actions == [
        {
            "kind": "tool_call",
            "name": "browser.search",
            "status": "completed",
            "detail": "",
        }
    ]


def test_file_condition_watch_fires_once_and_delivers_when_present(tmp_path):
    state = State(tmp_path / "state.sqlite3")
    spoken = []
    watched = tmp_path / "ready.flag"
    try:
        state.upsert_user("u1", "Alex", "sir", "owner")
        state.set_presence("u1", "voice", 1.0, True)
        state.set_kv("presence.active_user", "u1")
        watch_id = state.create_condition_watch(
            "watch-file",
            "file_exists",
            {"path": str(watched)},
            "The file exists now.",
            "u1",
            reason="You asked me to watch for the file.",
            priority=10,
            check_interval=1,
        )
        engine = ProactiveEngine(
            state,
            {
                "enabled": True,
                "quiet_hours_start": "03:00",
                "quiet_hours_end": "03:01",
            },
            spoken.append,
        )

        assert engine.tick() is False
        assert state.condition_watches("u1", active_only=True)[0]["id"] == watch_id

        watched.write_text("ready", encoding="utf-8")
        state._db.execute(
            "UPDATE condition_watches SET last_checked=NULL WHERE id=?",
            (watch_id,),
        )
        state._db.commit()

        assert engine.tick() is True
        assert spoken == ["The file exists now."]
        assert state.condition_watches("u1", active_only=True) == []
        assert engine.tick() is False
        assert spoken == ["The file exists now."]
    finally:
        state.close()


def test_router_can_create_real_openclaw_condition_watch(tmp_path):
    state = State(tmp_path / "state.sqlite3")
    try:
        state.upsert_user("u1", "Alex", "sir", "owner")
        router = _router(state, tmp_path)
        reply = router._local(
            "tell me when OpenClaw is back",
            "u1",
        )
        assert "OpenClaw is healthy again" in str(reply)
        watches = state.condition_watches("u1", active_only=True)
        assert len(watches) == 1
        assert watches[0]["kind"] == "openclaw_ready"
        assert "OpenClaw" in watches[0]["message"]
    finally:
        state.close()
