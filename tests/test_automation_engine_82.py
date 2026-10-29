from jervis.automation_engine import AutomationStore, Rule
from jervis.capabilities import Principal

import pytest


def test_automation_is_disabled_by_default_and_never_executes(tmp_path):
    owner = Principal("owner", "owner", True)
    store = AutomationStore(tmp_path / "rules.sqlite3")
    try:
        rule = store.create(owner, Rule("system.degraded", "notify",
                                        "system.status.read", "host"))
        eid = "f" * 32
        assert store.match_event(owner,event_id=eid,event_code="system.degraded",now=100) == []
        assert store.set_enabled(owner,rule,True)
        assert len(store.match_event(owner,event_id=eid,event_code="system.degraded",
                                     now=100,dry_run=True)) == 1
        result = store.match_event(owner,event_id=eid,event_code="system.degraded",now=100)
        assert result[0]["status"] == "waiting_approval"
        assert store.match_event(owner,event_id=eid,event_code="system.degraded",now=200)==[]
        assert store.match_event(owner,event_id="e"*32,
                                 event_code="system.degraded",now=130)==[]
        assert len(store.match_event(owner,event_id="d"*32,
                                     event_code="system.degraded",now=200)) == 1
        assert store.db.execute("SELECT COUNT(*) FROM pending_actions").fetchone()[0] == 2
    finally:
        store.close()


def test_owner_only_and_event_validation(tmp_path):
    owner = Principal("owner","owner",True)
    guest = Principal("visitor","known",True)
    store = AutomationStore(tmp_path / "rules.sqlite3")
    try:
        with pytest.raises(PermissionError):
            store.create(guest,Rule("test.event","notify","system.status.read","host"))
        rule = store.create(owner,Rule("test.event","notify","system.status.read","host"))
        with pytest.raises(PermissionError):
            store.set_enabled(guest,rule,True)
        with pytest.raises(ValueError):
            store.match_event(owner,event_id="not-an-id",event_code="test.event")
    finally:
        store.close()
