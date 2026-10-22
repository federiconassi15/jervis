"""Failure-injection coverage for the native self-updater.

Each test uses temporary paths and stubs downloads, binaries, and platform
effects; neither external releases nor host executables are modified.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from jervis import updater
from jervis.paths import Paths


def paths_for(tmp_path):
    paths = Paths(
        root=tmp_path,
        config=tmp_path / "config",
        data=tmp_path / "data",
        logs=tmp_path / "logs",
        cache=tmp_path / "cache",
    )
    paths.ensure()
    return paths


def release(version="v8.0.1"):
    return {
        "tag_name": version,
        "draft": False,
        "prerelease": False,
        "assets": [
            {"name": "jervis-test", "browser_download_url": "https://example.invalid/binary"},
            {"name": "SHA256SUMS", "browser_download_url": "https://example.invalid/checksums"},
        ],
    }


@pytest.mark.parametrize("fault", [
    "download", "checksum_missing", "checksum_mismatch",
    "smoke", "replacement",
])
def test_failed_native_update_attempts_snapshot_rollback(monkeypatch, tmp_path, fault):
    paths = paths_for(tmp_path)
    monkeypatch.setattr(updater, "_releases", lambda _repo: [release()])
    monkeypatch.setattr(updater, "VERSION_INFO", (8, 0, 0))
    monkeypatch.setattr(updater.sys, "frozen", True, raising=False)
    current_binary = tmp_path / "jervis-running"
    current_binary.write_bytes(b"current")
    monkeypatch.setattr(updater.sys, "executable", str(current_binary))
    monkeypatch.setattr(updater, "_asset_name", lambda: "jervis-test")
    saved = []
    restored = []
    replaced = []
    monkeypatch.setattr(updater, "create_snapshot", lambda *a, **k: saved.append("guard") or SimpleNamespace(id="guard"))
    monkeypatch.setattr(updater, "restore_snapshot", lambda snapshot_id, **k: restored.append(snapshot_id))

    expected_hash = hashlib.sha256(b"future-binary").hexdigest()

    def download(url, target):
        if fault == "download":
            raise OSError("network interrupted")
        if url.endswith("/binary"):
            target.write_bytes(b"future-binary")
        else:
            digest = "0" * 64 if fault == "checksum_mismatch" else expected_hash
            name = "missing-binary" if fault == "checksum_missing" else "jervis-test"
            target.write_text(digest + "  " + name + "\n", encoding="utf-8")

    monkeypatch.setattr(updater, "_download", download)
    monkeypatch.setattr(
        updater, "_smoke_binary",
        lambda _path: (False, "binary crashed") if fault == "smoke" else (True, "ok"),
    )

    def replace(*_args):
        replaced.append(True)
        if fault == "replacement":
            raise OSError("replacement denied")

    monkeypatch.setattr(updater, "_replace_native", replace)
    result = updater.apply_update(paths=paths)
    assert not result.ok
    assert result.target == "8.0.1"
    assert result.snapshot_id == "guard"
    assert "rollback was attempted" in result.detail
    assert saved == ["guard"]
    assert restored == ["guard"]
    assert current_binary.read_bytes() == b"current"
    assert bool(replaced) == (fault == "replacement")


def test_no_update_does_not_snapshot_or_download(monkeypatch, tmp_path):
    paths = paths_for(tmp_path)
    monkeypatch.setattr(updater, "_releases", lambda _repo: [release("v8.0.0")])
    monkeypatch.setattr(updater, "VERSION_INFO", (8, 0, 0))
    monkeypatch.setattr(
        updater, "create_snapshot",
        lambda *a, **k: pytest.fail("snapshot created despite no update"),
    )
    monkeypatch.setattr(
        updater, "_download",
        lambda *a, **k: pytest.fail("download started despite no update"),
    )
    result = updater.apply_update(paths=paths)
    assert result.ok
    assert result.detail == "already current"
    assert not result.restart_required


def test_source_install_never_replaces_host_executable(monkeypatch, tmp_path):
    paths = paths_for(tmp_path)
    monkeypatch.setattr(updater, "_releases", lambda _repo: [release()])
    monkeypatch.setattr(updater, "VERSION_INFO", (8, 0, 0))
    monkeypatch.setattr(updater.sys, "frozen", False, raising=False)
    monkeypatch.setattr(
        updater, "create_snapshot",
        lambda *a, **k: pytest.fail("source install was mutated"),
    )
    result = updater.apply_update(paths=paths)
    assert not result.ok
    assert "source installs" in result.detail
