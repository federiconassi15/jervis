"""8.2 read-only resource monitoring consent and privacy tests."""
from types import SimpleNamespace

import pytest

from jervis import system_awareness as awareness


def test_sampling_denied_without_consent(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("OS metrics must not be read without consent")
    monkeypatch.setattr(awareness.psutil, "cpu_percent", forbidden)
    with pytest.raises(PermissionError):
        awareness.sample_system()


def test_bounded_snapshot_never_includes_identity_or_process_details(monkeypatch, tmp_path):
    monkeypatch.setattr(awareness.psutil, "cpu_percent", lambda **kwargs: 15.123)
    monkeypatch.setattr(awareness.psutil, "virtual_memory", lambda:
                        SimpleNamespace(percent=22.456, available=104857600))
    monkeypatch.setattr(awareness.psutil, "disk_usage", lambda root:
                        SimpleNamespace(percent=61.789, free=209715200))
    monkeypatch.setattr(awareness.psutil, "sensors_battery", lambda: None)
    snap = awareness.sample_system(consent=True, disk_root=tmp_path, clock=lambda: 10)
    assert snap.cpu_percent == 15.1
    assert snap.memory_percent == 22.5
    assert snap.memory_available_mib == 100
    assert snap.disk_free_mib == 200
    assert snap.battery_percent is None
    assert set(snap.__dict__) == {
        "sampled_at", "cpu_percent", "memory_percent", "memory_available_mib",
        "disk_percent", "disk_free_mib", "battery_percent", "on_ac_power",
    }
