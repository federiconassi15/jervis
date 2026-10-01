from __future__ import annotations

import os
from pathlib import Path

import scripts.native_entry as native_entry


def test_first_install_rolls_back_to_no_binary(tmp_path: Path):
    source = tmp_path / "downloaded"
    target = tmp_path / "bin" / "jervis"
    source.write_bytes(b"new")

    backup = native_entry.install_native_copy(source, target)
    assert backup is None
    assert target.read_bytes() == b"new"

    native_entry.rollback_native_copy(target, backup)
    assert not target.exists()


def test_upgrade_rollback_restores_previous_binary(tmp_path: Path):
    source = tmp_path / "downloaded"
    target = tmp_path / "bin" / "jervis"
    target.parent.mkdir(parents=True)
    source.write_bytes(b"new")
    target.write_bytes(b"old")

    backup = native_entry.install_native_copy(source, target)
    assert backup is not None
    assert target.read_bytes() == b"new"

    native_entry.rollback_native_copy(target, backup)
    assert target.read_bytes() == b"old"
    assert not backup.exists()


def test_success_discards_backup(tmp_path: Path):
    source = tmp_path / "downloaded"
    target = tmp_path / "bin" / "jervis"
    target.parent.mkdir(parents=True)
    source.write_bytes(b"new")
    target.write_bytes(b"old")

    backup = native_entry.install_native_copy(source, target)
    assert backup is not None
    native_entry.commit_native_copy(backup)

    assert target.read_bytes() == b"new"
    assert not backup.exists()


def test_exit_code_normalization():
    assert native_entry._exit_code(SystemExit()) == 0
    assert native_entry._exit_code(SystemExit(0)) == 0
    assert native_entry._exit_code(SystemExit(130)) == 130
    assert native_entry._exit_code(SystemExit("failed")) == 1
