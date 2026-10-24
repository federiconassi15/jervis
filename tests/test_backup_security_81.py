"""Backup and snapshot security regression checks for 8.1."""
from __future__ import annotations

import io
import json
import os
import tarfile

import pytest

import jervis.snapshots as snapshot_module
from jervis.backup import restore_backup
from jervis.encrypted_backup import create_encrypted_backup, restore_encrypted_backup
from jervis.paths import Paths
from jervis.snapshots import create_snapshot


class NoService:
    def service_installed(self):
        return False


def _paths(tmp_path):
    p = Paths(tmp_path, tmp_path / "config", tmp_path / "data",
              tmp_path / "logs", tmp_path / "cache")
    p.ensure()
    return p


def test_snapshot_ids_are_unique_under_fast_repeated_creates(tmp_path):
    p = _paths(tmp_path)
    first = create_snapshot("repeat", paths=p)
    second = create_snapshot("repeat", paths=p)
    assert first.id != second.id
    assert len(list((p.data / "snapshots").glob("*.tar.gz"))) == 2


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission semantics")
def test_snapshot_files_are_private(tmp_path):
    p = _paths(tmp_path)
    (p.config / "config.json").write_text('{"private":"secret"}')
    snap = create_snapshot("private", paths=p)
    assert (p.data / "snapshots").stat().st_mode & 0o077 == 0
    assert __import__("pathlib").Path(snap.archive).stat().st_mode & 0o077 == 0


def test_encrypted_restoration_roundtrip(monkeypatch, tmp_path):
    p = _paths(tmp_path)
    monkeypatch.setattr(snapshot_module, "current_platform", NoService)
    value = p.data / "important.txt"
    value.write_text("original")
    encrypted = tmp_path / "export.jenc"
    create_encrypted_backup(encrypted, "strong-enough backup phrase", paths=p)
    assert encrypted.is_file()
    value.write_text("changed")
    restored = restore_encrypted_backup(encrypted, "strong-enough backup phrase", paths=p)
    assert restored
    assert value.read_text() == "original"
    # Decrypted imported archive is removed after the restore.
    assert not (p.data / "snapshots" / (restored + ".tar.gz")).exists()


def test_invalid_plain_backup_id_rejected_without_state_changes(tmp_path):
    p = _paths(tmp_path)
    (p.data / "important.txt").write_text("do not touch")
    path = tmp_path / "malicious.tar.gz"
    metadata = json.dumps({
        "id": "../../unsafe", "created_at": 0, "reason": "evil",
        "version": "8.0.0", "archive": "/tmp/unsafe", "includes_binary": False,
    }).encode("utf-8")
    with tarfile.open(path, "w:gz") as tar:
        entry = tarfile.TarInfo("snapshot.json")
        entry.size = len(metadata)
        tar.addfile(entry, io.BytesIO(metadata))
    with pytest.raises(ValueError, match="identifier"):
        restore_backup(path, paths=p)
    assert (p.data / "important.txt").read_text() == "do not touch"
    assert not list((p.data / "snapshots").glob("*.tar.gz"))
