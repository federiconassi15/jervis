from __future__ import annotations

import copy

import pytest

from jervis.config import DEFAULT_CONFIG, load, save, validate


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
