from __future__ import annotations

from pathlib import Path

from jervis.models import Permission
from jervis.presence import PresenceManager
from jervis.router import BrainRouter
from jervis.state import State


class FakeBrain:
    def __init__(self) -> None:
        self.agent = "main"
        self.calls = []

    def ask(
        self,
        message: str,
        session_key: str,
        thinking: str | None = None,
    ):
        self.calls.append((message, session_key, self.agent, thinking))

        class Reply:
            ok = True
            text = "openclaw reply"
            error = ""

        return Reply()


def test_presence_enter_and_timeout(tmp_path):
    state = State(tmp_path / "state.sqlite3")
    try:
        state.upsert_user("u1", "Alex", "sir", "owner")
        presence = PresenceManager(state, timeout_seconds=30)
        presence.seen("u1", "voice", 0.9)
        assert [item["name"] for item in presence.active()] == ["Alex"]

        seen_at = float(state.presence(present_only=True)[0]["seen_at"])
        assert presence.sweep(now=seen_at + 31) == ["u1"]
        assert presence.active() == []
        assert [row["kind"] for row in state.recent_events(10)] == [
            "presence_entered",
            "presence_left",
        ]
    finally:
        state.close()


def test_router_handles_local_before_openclaw(tmp_path):
    state = State(tmp_path / "state.sqlite3")
    try:
        state.upsert_user("u1", "Alex", "sir", "owner")
        fake = FakeBrain()
        paths = type(
            "Paths",
            (),
            {
                "data": tmp_path / "data",
                "root": tmp_path / "root",
            },
        )()
        router = BrainRouter(state, paths, fake)
        reply = router.ask("who am i", "u1")
        assert reply.route == "local"
        assert reply.text == "You're Alex."
        assert fake.calls == []
    finally:
        state.close()


def test_router_falls_back_to_openclaw(tmp_path):
    state = State(tmp_path / "state.sqlite3")
    try:
        state.upsert_user("u1", "Alex", "sir", "owner")
        fake = FakeBrain()
        paths = type(
            "Paths",
            (),
            {
                "data": tmp_path / "data",
                "root": tmp_path / "root",
            },
        )()
        router = BrainRouter(state, paths, fake)
        reply = router.ask("explain orbital mechanics", "u1")
        assert reply.route == "openclaw:fast"
        assert reply.text == "openclaw reply"
        assert fake.calls[0][1] == "jervis:u1"
    finally:
        state.close()


def test_skill_permissions_default_to_known_user(tmp_path):
    root = tmp_path / "skills"
    skill_dir = root / "hello"
    skill_dir.mkdir(parents=True)
    (skill_dir / "skill.py").write_text(
        "DESCRIPTION='hello skill'\n"
        "def handle(text, context):\n"
        "    return 'hello' if text == 'hello' else None\n",
        encoding="utf-8",
    )

    from jervis.skills import SkillManager

    state = State(tmp_path / "state.sqlite3")
    try:
        manager = SkillManager([root])
        manager.discover()
        assert manager.skills["hello"].permission is Permission.KNOWN_USER
        assert manager.route("hello", {}, state=state, user_id=None)[0] is None

        state.upsert_user("u1", "Alex", "sir", "known")
        assert manager.route("hello", {}, state=state, user_id="u1")[0] == "hello"
    finally:
        state.close()


def test_router_memory_is_per_user(tmp_path):
    state = State(tmp_path / "state.sqlite3")
    try:
        state.upsert_user("u1", "Alex", "sir", "owner")
        state.upsert_user("u2", "Sam", None, "known")
        fake = FakeBrain()
        paths = type(
            "Paths",
            (),
            {"data": tmp_path / "data", "root": tmp_path / "root"},
        )()
        router = BrainRouter(state, paths, fake, {"brain": {}})

        saved = router.ask("remember that I like synthwave", "u1")
        assert saved.route == "local"
        assert "synthwave" in router.ask("what do you remember", "u1").text
        assert "synthwave" not in router.ask("what do you remember", "u2").text
    finally:
        state.close()


def test_router_deep_tier_uses_high_thinking(tmp_path):
    state = State(tmp_path / "state.sqlite3")
    try:
        state.upsert_user("u1", "Alex", "sir", "owner")
        fake = FakeBrain()
        paths = type(
            "Paths",
            (),
            {"data": tmp_path / "data", "root": tmp_path / "root"},
        )()
        router = BrainRouter(
            state,
            paths,
            fake,
            {"brain": {"deep_thinking": "high"}},
        )
        reply = router.ask("analyze this architecture", "u1")
        assert reply.route == "openclaw:deep"
        assert fake.calls[0][3] == "high"
    finally:
        state.close()


def test_proactive_queue_waits_for_presence(tmp_path):
    from jervis.proactive import ProactiveEngine

    state = State(tmp_path / "state.sqlite3")
    announced = []
    try:
        state.upsert_user("u1", "Alex", "sir", "owner")
        engine = ProactiveEngine(
            state,
            {
                "enabled": True,
                "quiet_hours_start": "00:00",
                "quiet_hours_end": "00:00",
            },
            announced.append,
        )
        engine.queue("test", "hello", "u1")
        assert not engine.tick()
        state.set_presence("u1", "voice", 1.0, True)
        assert engine.tick()
        assert announced == ["hello"]
        assert not engine.tick()
    finally:
        state.close()
