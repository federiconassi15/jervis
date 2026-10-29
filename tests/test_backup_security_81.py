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



def test_encrypted_restore_exclusive_import_race(tmp_path, monkeypatch):
    """A competing snapshot published during import is never overwritten."""
    from pathlib import Path

    import jervis.encrypted_backup as module

    p = _paths(tmp_path)
    (p.data / "important.txt").write_text("original")
    encrypted = tmp_path / "export.jenc"
    create_encrypted_backup(encrypted, "strong-enough backup phrase", paths=p)
    with __import__("tempfile").TemporaryDirectory() as staging:
        plain = module.decrypt_file(encrypted, Path(staging) / "plain.tar.gz",
                                    "strong-enough backup phrase")
        identifier = module._verify_restorable_archive(plain)
    dest = p.data / "snapshots" / (identifier + ".tar.gz")
    original_open = module.os.open

    def racing_open(path, flags, *args, **kwargs):
        if Path(path) == dest:
            dest.write_bytes(b"another writer's snapshot")
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(module.os, "open", racing_open)
    with pytest.raises(FileExistsError):
        restore_encrypted_backup(encrypted, "strong-enough backup phrase", paths=p)
    assert dest.read_bytes() == b"another writer's snapshot"
    assert (p.data / "important.txt").read_text() == "original"


def test_encrypted_restore_does_not_unlink_replaced_import(tmp_path, monkeypatch):
    """Cleanup must not remove a new owner of a previously imported pathname."""
    from pathlib import Path

    import jervis.encrypted_backup as module
    import jervis.snapshots as snapshots

    p = _paths(tmp_path)
    (p.data / "important.txt").write_text("original")
    encrypted = tmp_path / "export.jenc"
    create_encrypted_backup(encrypted, "strong-enough backup phrase", paths=p)
    with __import__("tempfile").TemporaryDirectory() as staging:
        plain = module.decrypt_file(encrypted, Path(staging) / "plain.tar.gz",
                                    "strong-enough backup phrase")
        identifier = module._verify_restorable_archive(plain)
    dest = p.data / "snapshots" / (identifier + ".tar.gz")

    def replacement(*args, **kwargs):
        dest.unlink()
        dest.write_bytes(b"other owner")
        raise RuntimeError("Simulated racing restorer")

    monkeypatch.setattr(snapshots, "restore_snapshot", replacement)
    with pytest.raises(RuntimeError, match="racing"):
        restore_encrypted_backup(encrypted, "strong-enough backup phrase", paths=p)
    assert dest.read_bytes() == b"other owner"



def test_encrypted_export_never_creates_plain_snapshot(tmp_path, monkeypatch):
    import jervis.snapshots as snapshots

    p = _paths(tmp_path)
    (p.config / "config.json").write_text('{"name":"offline"}')
    (p.data / "important.txt").write_text("PRIVATE-DATA-NOT-ON-DISK")
    db = p.data / "jervis.sqlite3"
    import sqlite3
    with sqlite3.connect(db) as connection:
        connection.execute("CREATE TABLE sample(data TEXT)")
        connection.execute("INSERT INTO sample VALUES('persistent')")
    def forbidden_snapshot(*args, **kwargs):
        raise AssertionError("Encrypted export must not call create_snapshot")
    monkeypatch.setattr(snapshots, "create_snapshot", forbidden_snapshot)
    output = tmp_path / "export.jenc"
    create_encrypted_backup(output, "strong-enough backup phrase", paths=p)
    assert not list((p.data / "snapshots").glob("*.tar.gz"))
    assert b"PRIVATE-DATA-NOT-ON-DISK" not in output.read_bytes()
    assert not list(tmp_path.glob(".jervis-enc-*"))
    from jervis.encrypted_backup import decrypt_file, _verify_restorable_archive
    plain = tmp_path / "decrypted-in-test-only.tar.gz"
    decrypt_file(output, plain, "strong-enough backup phrase")
    assert _verify_restorable_archive(plain)


def test_encrypted_export_refuses_symlinked_private_files(tmp_path):
    p = _paths(tmp_path)
    secret = tmp_path / "private.txt"
    secret.write_text("do-not-follow")
    link = p.config / "linked.txt"
    try:
        link.symlink_to(secret)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks unavailable")
    destination = tmp_path / "export.jenc"
    with pytest.raises(ValueError, match="symlink"):
        create_encrypted_backup(destination, "strong-enough backup phrase", paths=p)
    assert not destination.exists()
    assert not list(tmp_path.glob(".jervis-enc-*"))
