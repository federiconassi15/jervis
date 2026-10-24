"""Declarative-only plugin execution boundaries."""
import json

import pytest

from jervis.plugin_engine import discover_commands, invoke_static_plugin


def _write(root, dirname, obj):
    directory = root / dirname
    directory.mkdir()
    (directory / "plugin.json").write_text(json.dumps(obj))


def test_safe_static_command(tmp_path):
    _write(tmp_path, "demo", {
        "id": "test.demo", "version": "1.0.0", "permissions": [],
        "commands": [{"name": "greet", "type": "response", "text": "Hello."}],
    })
    assert invoke_static_plugin(tmp_path, "test.demo", "greet") == "Hello."
    with pytest.raises(ValueError):
        invoke_static_plugin(tmp_path, "test.demo", "delete-all")


def test_arbitrary_code_and_permissions_are_never_executed(tmp_path):
    _write(tmp_path, "unsafe", {
        "id": "unsafe.test", "version": "1.0.0",
        "permissions": ["filesystem.write"],
        "commands": [{"name": "shell", "type": "python", "code": "print(1)"}],
    })
    assert discover_commands(tmp_path) == []


def test_large_manifest_is_rejected(tmp_path):
    directory = tmp_path / "giant"
    directory.mkdir()
    (directory / "plugin.json").write_text(" " * 20000)
    assert discover_commands(tmp_path) == []


def test_symlinked_manifest_is_ignored(tmp_path):
    outside = tmp_path / "outside.json"
    outside.write_text(json.dumps({
        "id": "test.plugin", "version": "1.0.0",
        "commands": [{"name": "test", "type": "response", "text": "Hi"}]
    }))
    directory = tmp_path / "link"
    directory.mkdir()
    try:
        (directory / "plugin.json").symlink_to(outside)
    except (NotImplementedError, OSError):
        pytest.skip("Symlinks unavailable")
    assert discover_commands(tmp_path) == []
