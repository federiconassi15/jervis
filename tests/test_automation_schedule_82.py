"""Time triggers feed Jervis's approval queue without executing actions."""
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from jervis.automation_schedule import Schedule, TimeAutomationStore, _next_daily
from jervis.capabilities import Principal


def _owner():
    return Principal("owner", "owner", True)


def test_interval_schedule_requires_enable_and_avoids_missed_backlog(tmp_path):
    store = TimeAutomationStore(tmp_path / "rules.sqlite")
    try:
        rule = store.add_schedule(_owner(), Schedule("interval", seconds=60),
                                  action="notify", capability="system.status.read",
                                  scope="host", now=100)
        assert store.poll(_owner(), now=100000) == []
        assert store.set_enabled(_owner(), rule, True)
        first = store.poll(_owner(), now=100000)
        assert len(first) == 1
        assert first[0]["status"] == "waiting_approval"
        assert store.poll(_owner(), now=100000) == []
        assert store.poll(_owner(), now=100010) == []
        assert len(store.poll(_owner(), now=100061)) == 1
        assert len(store.db.execute("SELECT id FROM pending_actions").fetchall()) == 2
    finally:
        store.close()


def test_isolated_per_user_and_disabled_by_default(tmp_path):
    store = TimeAutomationStore(tmp_path / "rules.sqlite")
    try:
        rule = store.add_schedule(_owner(), Schedule("interval", seconds=60),
                                  action="notify", capability="system.status.read",
                                  scope="host", now=0)
        store.set_enabled(_owner(), rule, True)
        other = Principal("other", "owner", True)
        assert store.poll(other, now=90) == []
        with pytest.raises(PermissionError):
            store.poll(Principal("guest", "guest", True), now=90)
        assert len(store.poll(_owner(), now=90)) == 1
    finally:
        store.close()


def test_nonexistent_daily_clock_is_skipped_and_fold_is_first():
    zone = ZoneInfo("Europe/Berlin")
    schedule = Schedule("daily_local", timezone="Europe/Berlin", hour=2, minute=30)
    start = datetime(2026, 3, 28, 12, tzinfo=zone).timestamp()
    next_due = datetime.fromtimestamp(_next_daily(schedule, start), zone)
    assert (next_due.month, next_due.day, next_due.hour, next_due.minute) == (3,30,2,30)
    autumn = datetime(2026, 10, 24, 12, tzinfo=zone).timestamp()
    fold = datetime.fromtimestamp(_next_daily(schedule, autumn), zone)
    assert (fold.month, fold.day, fold.fold) == (10,25,0)


def test_refuse_invalid_intervals_or_timezones(tmp_path):
    store = TimeAutomationStore(tmp_path / "rules.sqlite")
    try:
        with pytest.raises(ValueError):
            store.add_schedule(_owner(), Schedule("interval", seconds=1),
                               action="notify", capability="system.status.read",
                               scope="host")
        with pytest.raises(ValueError):
            store.add_schedule(_owner(), Schedule("daily_local",
                                                 timezone="Invalid/Nowhere"),
                               action="notify", capability="system.status.read",
                               scope="host")
    finally:
        store.close()
