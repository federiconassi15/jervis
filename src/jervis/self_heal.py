"""Jervis 8.1 self-healing: bounded diagnosis and reversible, explicit repairs.

Reads use read-only database mode. The safe automatic policy is limited to
owner-owned local file permissions. It never installs software, restarts
services, contacts providers, or rolls back data without operator consent.
"""
from __future__ import annotations

import json
import os
import sqlite3
import stat
from dataclasses import asdict, dataclass
from pathlib import Path

from .paths import Paths
from .recovery_verify import verify_snapshot_archive


@dataclass(frozen=True)
class Finding:
    code: str
    severity: str
    message: str
    remedy: str | None = None
    safe_auto: bool = False

    def as_dict(self):
        return asdict(self)


def diagnose(paths: Paths | None = None) -> list[Finding]:
    paths = paths or Paths.resolve()
    findings: list[Finding] = []
    config = paths.config / "config.json"
    database = paths.data / "jervis.sqlite3"
    if not config.exists():
        findings.append(Finding("config.missing", "warning",
                                "No configuration is installed yet.",
                                "Run jervis install"))
    else:
        try:
            from .config import validate, _merge, DEFAULT_CONFIG

            raw = json.loads(config.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("Configuration must contain a JSON object")
            validate(_merge(DEFAULT_CONFIG, raw))
        except (ValueError, TypeError, KeyError, OSError):
            findings.append(Finding("config.invalid", "critical",
                                    "Local configuration is unreadable or invalid.",
                                    "Review configuration; restore a verified snapshot"))
    if database.is_file():
        try:
            # SQLite URI query escape required for '#' and '?' in paths.
            from urllib.parse import quote

            uri = "file:" + quote(database.resolve().as_posix(), safe="/:") + "?mode=ro"
            with sqlite3.connect(uri, uri=True, timeout=1.0) as db:
                row = db.execute("PRAGMA quick_check(1)").fetchone()
            if not row or row[0] != "ok":
                findings.append(Finding("database.invalid", "critical",
                                        "The local database failed integrity checks.",
                                        "Inspect backups; do not overwrite corrupt data"))
        except (sqlite3.Error, OSError):
            findings.append(Finding("database.unreadable", "critical",
                                    "The local database could not be inspected.",
                                    "Inspect file permissions and recovery snapshots"))

    snapshot_dir = paths.data / "snapshots"
    if snapshot_dir.is_dir():
        bad = 0
        for index, archive in enumerate(snapshot_dir.glob("*.tar.gz")):
            if index >= 128:
                findings.append(Finding("snapshots.limit", "warning",
                                        "Too many snapshots to inspect in one pass."))
                break
            if not verify_snapshot_archive(archive):
                bad += 1
        if bad:
            findings.append(Finding("snapshots.invalid", "warning",
                                    f"{bad} recovery archive(s) failed validation.",
                                    "Create a fresh backup and inspect the damaged archives"))

    if os.name != "nt":
        for target in (paths.config, paths.data, config, database):
            if not target.exists() or target.is_symlink():
                continue
            expected = 0o700 if target.is_dir() else 0o600
            actual = stat.S_IMODE(target.stat().st_mode)
            if actual & 0o077:
                findings.append(Finding(
                    "permissions.unsafe", "warning",
                    "Local Jervis state permissions allow group/other access.",
                    "Run jervis self-heal apply permissions",
                    safe_auto=True,
                ))
                break
    if not findings:
        findings.append(Finding("healthy.local", "info",
                                "Local files and recoverable snapshots passed checks."))
    return findings


def apply_safe_permissions(*, paths: Paths | None = None, consent: bool = False) -> list[str]:
    """Narrow, idempotent change with guard snapshot. Never alters symlinks."""
    if not consent:
        raise PermissionError("Explicit consent required for self-healing changes")
    paths = paths or Paths.resolve()
    targets = [paths.config, paths.data,
               paths.config / "config.json", paths.data / "jervis.sqlite3"]
    unsafe = []
    # Refuse suspicious links on every OS, including platforms where Jervis
    # cannot safely alter native ACLs.
    for target in targets:
        if target.is_symlink():
            raise ValueError("Refusing to modify symlinked private state")
    if os.name == "nt":
        return ["Windows ACLs are not changed automatically"]
    for target in targets:
        if target.is_symlink():
            raise ValueError("Refusing to modify symlinked private state")
        if target.exists():
            if not target.is_dir() and not target.is_file():
                raise ValueError("Unexpected private state file type")
            expected = 0o700 if target.is_dir() else 0o600
            if stat.S_IMODE(target.stat().st_mode) & 0o077:
                unsafe.append((target, expected))
    if not unsafe:
        return ["Private file permissions already safe"]
    # Backup before changing private state; failure aborts modification.
    from .snapshots import create_snapshot

    create_snapshot("pre-safe-permissions", paths=paths, include_binary=False)
    changed = []
    for target, mode in unsafe:
        # Verify again after staging; don't follow switched symlinks.
        if target.is_symlink():
            raise ValueError("Refusing symlink switched during repair")
        target.chmod(mode)
        changed.append(target.name)
    return changed
