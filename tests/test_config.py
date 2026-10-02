from __future__ import annotations

import copy

import pytest

from jervis.config import DEFAULT_CONFIG, load, save, validate
from jervis.migrations import CURRENT_CONFIG_SCHEMA, migrate_config


def test_roundtrip(tmp_path):
    path = tmp_path / "config.json"
    save(path, DEFAULT_CONFIG)
    loaded = load(path)
    assert loaded["assistant"]["wake_acknowledgement"] == "Boss?"
    assert loaded["install"]["mode"] == "desktop"


def test_invalid_mode_rejected():
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["install"]["mode"] = "spaceship"
    with pytest.raises(ValueError):
        validate(config)


def test_invalid_threshold_order_rejected():
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["identity"]["strong_threshold"] = 0.5
    config["identity"]["session_threshold"] = 0.7
    with pytest.raises(ValueError):
        validate(config)


def test_schema_2_config_migrates_to_7_4_defaults():
    legacy = {
        "schema": 2,
        "assistant": {"name": "Jervis"},
        "presence": {
            "enabled": True,
            "timeout_seconds": 300,
        },
        "proactive": {
            "enabled": True,
            "quiet_hours_start": "23:00",
            "quiet_hours_end": "07:00",
        },
    }
    migrated, changes = migrate_config(legacy)
    assert migrated["schema"] == CURRENT_CONFIG_SCHEMA == 3
    assert migrated["continuity"]["session_summary_items"] == 3
    assert migrated["continuity"]["correction_context_turns"] == 6
    assert migrated["presence"]["return_window_seconds"] == 1800
    assert migrated["proactive"]["default_ttl_seconds"] == 86400
    assert any("schema 2 -> 3" in change for change in changes)
