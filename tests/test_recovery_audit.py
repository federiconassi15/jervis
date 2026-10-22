"""Recovery regressions: never destroy recovery points or strand a service.

All tests use temporary directories and fake platform adapters. They exercise
real tar archives, not just mocks of the validation routines.
"""
from __future__ import annotations

import io
import json
import shutil
import tarfile
from pathlib import Path

import pytest

from jervis import backup, snapshots
from jervis.paths import Paths


class FakeService:
    def __init__(self):
        self.stopped = 0
        self.started = 0

    def service_installed(self):
        return True

    def stop_service(self):
        self.stopped += 1

    def start_service(self):
        self.started += 1


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


def write_archive(path, snapshot_id, *, extra_member=None):
    metadata = dict(
        id=snapshot_id,
        created_at=1.0,
        reason="test",
        version="8.0.0",
        archive=str(path),
        includes_binary=False,
    )
    data = json.dumps(metadata).encode()
    with tarfile.open(path, "w:gz") as bundle:
        member = tarfile.TarInfo("snapshot.json")
        member.size = len(data)
        bundle.addfile(member, io.BytesIO(data))
        if extra_member is not None:
            bundle.addfile(extra_member[0], extra_member[1])


def test_same_second_snapshots_do_not_overwrite_each_other(tmp_path, monkeypatch):
    paths = paths_for(tmp_path)
    monkeypatch.setattr(snapshots.time, "strftime", lambda *_: "20261022-070000")
    value = paths.data / "value.txt"
    value.write_text("first", encoding="utf-8")
    first = snapshots.create_snapshot("recovery", paths=paths)
    before = Path(first.archive).read_bytes()
    value.write_text("second", encoding="utf-8")
    second = snapshots.create_snapshot("recovery", paths=paths)
    assert first.id != second.id
    assert Path(first.archive).read_bytes() == before
    assert Path(second.archive).exists()
    assert len(snapshots.list_snapshots(paths=paths)) == 2


@pytest.mark.parametrize("bad_id", [
    "../escape", "../../escape", "/absolute", "a/b", r"C:\Windows\Temp",
    "..", ".", "bad:name", "x" * 140,
])
def test_backup_rejects_hostile_snapshot_ids(tmp_path, bad_id):
    paths = paths_for(tmp_path)
    source = tmp_path / "hostile.tar.gz"
    write_archive(source, bad_id)
    with pytest.raises(ValueError, match="unsafe snapshot identifier"):
        backup.restore_backup(source, paths=paths)
    assert not (paths.data / "escape.tar.gz").exists()
    assert not list((paths.data / "snapshots").glob("*.tar.gz"))


def test_backup_collision_preserves_existing_recovery_point(tmp_path):
    paths = paths_for(tmp_path)
    first = snapshots.create_snapshot("existing", paths=paths)
    prior = Path(first.archive).read_bytes()
    imported = tmp_path / "conflicting.tar.gz"
    write_archive(imported, first.id)
    with pytest.raises(RuntimeError, match="conflicts"):
        backup.restore_backup(imported, paths=paths)
    assert Path(first.archive).read_bytes() == prior


@pytest.mark.parametrize("kind", ["traversal", "symlink", "device"])
def test_malicious_archive_rejected_before_service_stop(tmp_path, monkeypatch, kind):
    paths = paths_for(tmp_path)
    service = FakeService()
    monkeypatch.setattr(snapshots, "current_platform", lambda: service)
    archive = paths.data / "snapshots" / "malicious.tar.gz"
    archive.parent.mkdir(parents=True, exist_ok=True)
    if kind == "traversal":
        member = tarfile.TarInfo("../../escaped.txt")
        member.size = 3
        payload = io.BytesIO(b"bad")
    elif kind == "symlink":
        member = tarfile.TarInfo("config/evil")
        member.type = tarfile.SYMTYPE
        member.linkname = "../../escaped.txt"
        payload = None
    else:
        member = tarfile.TarInfo("config/device")
        member.type = tarfile.CHRTYPE
        member.devmajor = 1
        member.devminor = 3
        payload = None
    write_archive(archive, "malicious", extra_member=(member, payload))
    with pytest.raises(RuntimeError, match="unsafe|unsupported"):
        snapshots.restore_snapshot("malicious", paths=paths, make_guard=False, restore_binary=False)
    assert service.stopped == 0
    assert service.started == 0
    assert not (tmp_path / "escaped.txt").exists()


def test_malformed_snapshot_metadata_does_not_stop_service(tmp_path, monkeypatch):
    paths = paths_for(tmp_path)
    service = FakeService()
    monkeypatch.setattr(snapshots, "current_platform", lambda: service)
    archive = paths.data / "snapshots" / "invalid.tar.gz"
    archive.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "w:gz") as bundle:
        data = b"{not-json"
        member = tarfile.TarInfo("snapshot.json")
        member.size = len(data)
        bundle.addfile(member, io.BytesIO(data))
    with pytest.raises(json.JSONDecodeError):
        snapshots.restore_snapshot("invalid", paths=paths, make_guard=False, restore_binary=False)
    assert service.stopped == 0
    assert service.started == 0


def test_restore_copy_failure_restarts_previous_service(tmp_path, monkeypatch):
    paths = paths_for(tmp_path)
    original = paths.config / "config.json"
    original.write_text("original", encoding="utf-8")
    snap = snapshots.create_snapshot("known-good", paths=paths)
    original.write_text("changed", encoding="utf-8")
    service = FakeService()
    monkeypatch.setattr(snapshots, "current_platform", lambda: service)

    def denied(*_args, **_kwargs):
        raise PermissionError("copy denied")

    monkeypatch.setattr(snapshots.shutil, "copytree", denied)
    with pytest.raises(PermissionError, match="copy denied"):
        snapshots.restore_snapshot(snap.id, paths=paths, make_guard=False, restore_binary=False)
    assert service.stopped == 1
    assert service.started == 1


def test_recovery_roundtrip_preserves_backup_and_starts_service(tmp_path, monkeypatch):
    paths = paths_for(tmp_path)
    value = paths.data / "value.txt"
    value.write_text("before", encoding="utf-8")
    snap = snapshots.create_snapshot("stable", paths=paths)
    value.write_text("after", encoding="utf-8")
    service = FakeService()
    monkeypatch.setattr(snapshots, "current_platform", lambda: service)
    snapshots.restore_snapshot(snap.id, paths=paths, make_guard=False, restore_binary=False)
    assert value.read_text(encoding="utf-8") == "before"
    assert service.stopped == 1
    assert service.started == 1
