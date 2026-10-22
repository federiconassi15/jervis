from __future__ import annotations

import filecmp
import json
import re
import shutil
import tarfile
import tempfile
import time
from pathlib import Path

from .paths import Paths
from .snapshots import create_snapshot, restore_snapshot


def create_backup(destination: Path, *, paths: Paths | None = None) -> Path:
    resolved = paths or Paths.resolve()
    resolved.ensure()
    destination = destination.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)

    snap = create_snapshot("backup-staging", paths=resolved, include_binary=False)
    source = Path(snap.archive)
    shutil.copy2(source, destination)
    return destination


def restore_backup(source: Path, *, paths: Paths | None = None) -> None:
    resolved = paths or Paths.resolve()
    source = source.expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(str(source))

    with tarfile.open(source, "r:gz") as bundle:
        raw = bundle.extractfile("snapshot.json")
        if raw is None:
            raise RuntimeError("backup is missing snapshot metadata")
        metadata = json.loads(raw.read().decode("utf-8"))

    snapshot_id = metadata.get("id") if isinstance(metadata, dict) else None
    if not isinstance(snapshot_id, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", snapshot_id
    ):
        raise ValueError("backup has an unsafe snapshot identifier")

    snapshots = resolved.data / "snapshots"
    snapshots.mkdir(parents=True, exist_ok=True)
    imported = snapshots / (snapshot_id + ".tar.gz")
    if imported.exists() and not filecmp.cmp(source, imported, shallow=False):
        raise RuntimeError("backup snapshot ID conflicts with a different saved snapshot")

    create_snapshot("pre-backup-restore", paths=resolved, include_binary=False)
    if not imported.exists():
        shutil.copy2(source, imported)
    restore_snapshot(snapshot_id, paths=resolved, make_guard=False)
