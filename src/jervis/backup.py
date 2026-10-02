from __future__ import annotations

import json
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

    create_snapshot("pre-backup-restore", paths=resolved, include_binary=False)
    snapshots = resolved.data / "snapshots"
    snapshots.mkdir(parents=True, exist_ok=True)
    with tarfile.open(source, "r:gz") as bundle:
        raw = bundle.extractfile("snapshot.json")
        if raw is None:
            raise RuntimeError("backup is missing snapshot metadata")
        metadata = json.loads(raw.read().decode("utf-8"))

    imported = snapshots / (str(metadata["id"]) + ".tar.gz")
    shutil.copy2(source, imported)
    restore_snapshot(str(metadata["id"]), paths=resolved, make_guard=False)
