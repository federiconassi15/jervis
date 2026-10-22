"""Jervis 8.1 core regression tests."""
import json

from jervis.evolve import discover_plugins, health_summary, resolve_offline, render_plugins
from jervis.paths import Paths


def _paths(tmp_path):
    paths = Paths(tmp_path, tmp_path / "config", tmp_path / "data", tmp_path / "logs", tmp_path / "cache")
    paths.ensure()
    return paths


def test_offline_intents_are_deterministic():
    assert resolve_offline("  HeLLo ") == resolve_offline("hello")
    assert resolve_offline("status").name == "status"
    assert resolve_offline("delete all files") is None
    assert resolve_offline("turn off security") is None


def test_plugin_discovery_is_data_only(tmp_path):
    paths = _paths(tmp_path)
    directory = paths.data / "plugins" / "demo"
    directory.mkdir(parents=True)
    (directory / "plugin.json").write_text(json.dumps({
        "id": "demo.plugin", "version": "1.0.0", "description": "A safe demo",
        "permissions": ["status.read"]
    }))
    assert discover_plugins(paths.data / "plugins")[0].identifier == "demo.plugin"
    assert render_plugins(paths)[0]["permissions"] == ("status.read",)


def test_unauthorized_plugin_permissions_rejected(tmp_path):
    paths = _paths(tmp_path)
    directory = paths.data / "plugins" / "evil"
    directory.mkdir(parents=True)
    (directory / "plugin.json").write_text(json.dumps({
        "id": "evil", "version": "1.0.0", "permissions": ["filesystem.write"]
    }))
    assert discover_plugins(paths.data / "plugins") == []


def test_health_summary_missing_install_is_safe(tmp_path):
    paths = _paths(tmp_path)
    summary = health_summary(paths)
    assert summary["config_present"] is False
    assert summary["database_present"] is False
    assert summary["recovery_snapshots"] == 0
