"""Durable mission queue must never replay unsafe steps or bypass capabilities."""
from jervis.capabilities import Principal, CapabilityGrant
from jervis.mission_engine import MissionStep, MissionStore


def test_mission_owner_scopes_and_completion(tmp_path):
    owner = Principal("owner", "owner", True)
    remote = Principal("owner", "owner", True, "phone")
    other = Principal("other", "owner", True)
    store = MissionStore(tmp_path / "mission.db")
    try:
        mission = store.create(owner, (
            MissionStep("status", "system.status.read", "", {}, True),
        ))
        import pytest
        with pytest.raises(PermissionError):
            store.execute_next(mission, other, {"status": lambda _: "ok"})
        assert store.execute_next(mission, owner, {"status": lambda _: {"status": "ok"}}) == "completed"
        assert store.describe(mission, owner)["steps"][0]["status"] == "completed"
        assert store.execute_next(mission, owner, {"status": lambda _: "duplicate"}) == "completed"
        remote_mission = store.create(owner, (
            MissionStep("status", "system.status.read", "host", {}, True),
        ))
        assert store.execute_next(remote_mission, remote, {"status": lambda _: 1}) == "waiting_approval"
        grant = CapabilityGrant("owner", "system.status.read", "host", 10**12, "phone")
        assert store.execute_next(remote_mission, remote, {"status": lambda _: 1},
                                  grants=(grant,)) == "completed"
    finally:
        store.close()


def test_crash_recovery_does_not_repeat_non_idempotent_work(tmp_path):
    owner = Principal("owner", "owner", True)
    store = MissionStore(tmp_path / "mission.db")
    try:
        mission = store.create(owner, (
            MissionStep("write", "filesystem.write", str(tmp_path), {}, False),
            MissionStep("status", "system.status.read", "", {}, True),
        ))
        store.db.execute(
            "UPDATE steps SET status='running' WHERE mission_id=? AND position=0",
            (mission,),
        )
        assert store.recover() == (0, 1)
        assert store.describe(mission, owner)["status"] == "blocked"
        assert store.execute_next(mission, owner,
                                  {"write": lambda _: 1}) == "blocked"
        fresh = store.create(owner, (
            MissionStep("read", "system.status.read", "", {}, True),
        ))
        store.db.execute(
            "UPDATE steps SET status='running' WHERE mission_id=?", (fresh,)
        )
        assert store.recover() == (1, 0)
        assert store.execute_next(fresh, owner,
                                  {"read": lambda _: 1}) == "completed"
    finally:
        store.close()


def test_permission_checks_before_side_effects(tmp_path):
    owner = Principal("owner", "owner", True)
    store = MissionStore(tmp_path / "mission.db")
    calls = []
    try:
        mission = store.create(owner, (
            MissionStep("danger", "process.execute", "command:doctor", {}, False),
        ))
        assert store.execute_next(mission, owner,
                                  {"danger": lambda _: calls.append(1)}) == "waiting_approval"
        assert calls == []
        grant = CapabilityGrant("owner", "process.execute", "command:doctor", 10**12)
        assert store.execute_next(mission, owner, {"danger": lambda _: calls.append(1)},
                                  grants=(grant,), fresh_auth=True) == "completed"
        assert calls == [1]
    finally:
        store.close()
