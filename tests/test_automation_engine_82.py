"""Automation scheduling, event replay, owner boundaries and DST handling."""
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from jervis.automation_engine import Automation, AutomationStore, Trigger, _next_daily
from jervis.capabilities import Principal


def _owner():
    return Principal("alice", "owner", True)


def test_interval_trigger_backlog_and_persistence(tmp_path):
    db = tmp_path / "a.sqlite3"
    automation = Automation(
        trigger=Trigger("interval", interval_seconds=60),
        action="local.status", capability="system.status.read",
        scope="local-host", payload={},
        idempotent=True,
    )
    store = AutomationStore(db)
    rule = store.create(_owner(), automation, now=100)
    store.set_enabled(_owner(), rule, True)
    assert store.due(now=159) == []
    pending = store.due(now=50000)
    assert len(pending) == 1  # no backlog storm after downtime
    assert store.due(now=50000) == []
    assert len(store.pending(_owner())) == 1
    store.close()

    reopened = AutomationStore(db)
    assert len(reopened.pending(_owner())) == 1
    reopened.complete(_owner(), pending[0])
    assert reopened.pending(_owner()) == []
    reopened.close()


def test_event_dedupe_and_unauthorized_management(tmp_path):
    store = AutomationStore(tmp_path / "a.sqlite3")
    trigger = Trigger(kind="event", event_kind="device.offline")
    rule = store.create(_owner(), Automation(
        trigger=trigger, action="local.status",
        capability="system.status.read", scope="host", payload={},
    ))
    store.set_enabled(_owner(), rule, True)
    key = "a" * 32
    assert len(store.on_event("device.offline", key)) == 1
    assert store.on_event("device.offline", key) == []
    assert len(store.pending(_owner())) == 1
    with pytest.raises(PermissionError):
        store.set_enabled(Principal("bob", "owner", True), rule, False)
    with pytest.raises(PermissionError):
        store.create(Principal("bob", "guest", True),
                     Automation(trigger, "local.status", "system.status.read", "host", {}))
    store.close()


def test_interval_validation_and_code_injection_is_data(tmp_path):
    store = AutomationStore(tmp_path / "a.sqlite3")
    with pytest.raises(ValueError):
        store.create(_owner(), Automation(
            Trigger(kind="interval", interval_seconds=0),
            "local.status", "system.status.read", "host", {},
        ))
    with pytest.raises(ValueError):
        store.create(_owner(), Automation(
            Trigger(kind="interval", interval_seconds=60),
            "__import__('os').system('whoami')", "process.execute", "host", {},
        ))
    store.close()


def test_daylight_saving_gap_and_fold_are_defined():
    zone = ZoneInfo("Europe/Berlin")
    day = datetime(2026, 3, 28, 12, tzinfo=zone).timestamp()
    trigger = Trigger(kind="daily_local", timezone_name="Europe/Berlin", hour=2, minute=30)
    # March 29, 2026 is the spring-forward gap; schedule next valid local day.
    next_due = _next_daily(day, trigger)
    actual = datetime.fromtimestamp(next_due, zone)
    assert (actual.month, actual.day, actual.hour, actual.minute) == (3, 30, 2, 30)
    # October fold chooses first occurrence, never twice per day.
    late_oct = datetime(2026, 10, 24, 12, tzinfo=zone).timestamp()
    one = _next_daily(late_oct, trigger)
    when = datetime.fromtimestamp(one, zone)
    assert (when.month, when.day, when.fold) == (10, 25, 0)
    next_day = _next_daily(one + 5, trigger)
    assert datetime.fromtimestamp(next_day, zone).day == 26
