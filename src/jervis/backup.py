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

    # Validate all archive members before creating a restore guard or changing
    # any files. This also rejects malicious snapshot IDs and traversal.
    from .encrypted_backup import _verify_restorable_archive

    identifier = _verify_restorable_archive(source)
    create_snapshot("pre-backup-restore", paths=resolved, include_binary=False)
    snapshots = resolved.data / "snapshots"
    snapshots.mkdir(mode=0o700, parents=True, exist_ok=True)
    imported = snapshots / (identifier + ".tar.gz")
    if imported.exists() or imported.is_symlink():
        raise FileExistsError("An existing recovery snapshot has this ID")
    with tempfile.NamedTemporaryFile(
        prefix=".jervis-restore-", dir=snapshots, delete=False
    ) as staging:
        staged = Path(staging.name)
    try:
        shutil.copy2(source, staged)
        # Atomic create-no-overwrite semantics, even with a concurrent writer.
        import os

        os.link(staged, imported)
    finally:
        staged.unlink(missing_ok=True)
    restore_snapshot(identifier, paths=resolved, make_guard=False)
