"""Self-heal diagnosis does not damage state and needs explicit consent."""
import os
import sqlite3

import pytest

from jervis.paths import Paths
from jervis.self_heal import apply_safe_permissions, diagnose


def _paths(tmp_path):
    p = Paths(tmp_path, tmp_path / "config", tmp_path / "data",
              tmp_path / "logs", tmp_path / "cache")
    p.ensure()
    return p


def test_diagnosis_missing_config_does_not_write(tmp_path):
    paths = _paths(tmp_path)
    report = diagnose(paths)
    assert "config.missing" in [r.code for r in report]
    assert not (paths.config / "config.json").exists()


def test_diagnosis_rejects_corrupt_config_and_db(tmp_path):
    paths = _paths(tmp_path)
    (paths.config / "config.json").write_text("{invalid")
    (paths.data / "jervis.sqlite3").write_bytes(b"not-sqlite")
    report = diagnose(paths)
    codes = {r.code for r in report}
    assert "config.invalid" in codes
    assert "database.unreadable" in codes or "database.invalid" in codes
    assert (paths.data / "jervis.sqlite3").read_bytes() == b"not-sqlite"


def test_safe_repair_requires_consent(tmp_path):
    paths = _paths(tmp_path)
    with pytest.raises(PermissionError):
        apply_safe_permissions(paths=paths, consent=False)


@pytest.mark.skipif(os.name == "nt", reason="POSIX mode semantics")
def test_permission_repair_creates_guard_snapshot(tmp_path):
    paths = _paths(tmp_path)
    config = paths.config / "config.json"
    config.write_text("{}")
    config.chmod(0o644)
    report = diagnose(paths)
    assert any(r.code == "permissions.unsafe" for r in report)
    # A snapshot of mutable state must exist before the change.
    changed = apply_safe_permissions(paths=paths, consent=True)
    assert changed
    assert config.stat().st_mode & 0o077 == 0
    assert list((paths.data / "snapshots").glob("*.tar.gz"))


def test_refuse_state_symlink(tmp_path):
    paths = _paths(tmp_path)
    outside = tmp_path / "outside"
    outside.write_text("important")
    config = paths.config / "config.json"
    try:
        config.symlink_to(outside)
    except (NotImplementedError, OSError):
        pytest.skip("symlinks unavailable")
    with pytest.raises(ValueError, match="symlink"):
        apply_safe_permissions(paths=paths, consent=True)
    assert outside.read_text() == "important"
