"""Stream Jervis snapshot contents into an authenticated encrypted export.

Unlike create_snapshot(), this path never creates a plaintext tarball or a
temporary plaintext copy of the configuration/database on persistent storage.
SQLite's consistent backup is held in bounded process memory.
"""
from __future__ import annotations

import io
import json
import os
import secrets
import sqlite3
import stat
import tarfile
import tempfile
import time
from pathlib import Path
from urllib.parse import quote

from .paths import Paths
from .version import __version__

_MAX_UNCOMPRESSED = 2 * 1024 * 1024 * 1024
_MAX_ARCHIVE = 2 * 1024 * 1024 * 1024
_MAX_MEMBERS = 12000
_MAX_SQLITE_MEMORY = 128 * 1024 * 1024


class _EncryptedSink:
    """Write-only stream accepted by tarfile.open(mode='w|gz')."""

    def __init__(self, output, encryptor):
        self.output = output
        self.encryptor = encryptor
        self.count = 0

    def write(self, data: bytes) -> int:
        self.count += len(data)
        if self.count > _MAX_ARCHIVE:
            raise ValueError("Compressed recovery archive exceeds 2 GiB")
        self.output.write(self.encryptor.update(data))
        return len(data)

    def flush(self) -> None:
        self.output.flush()


class _SnapshotPacker:
    def __init__(self, archive: tarfile.TarFile):
        self.archive = archive
        self.members = 0
        self.total = 0

    def _count(self, size: int) -> None:
        self.members += 1
        self.total += size
        if self.members > _MAX_MEMBERS or self.total > _MAX_UNCOMPRESSED:
            raise ValueError("Recovery archive exceeds safe content limits")

    def directory(self, name: str) -> None:
        self._count(0)
        entry = tarfile.TarInfo(name.rstrip("/") + "/")
        entry.type = tarfile.DIRTYPE
        entry.mode = 0o700
        entry.mtime = int(time.time())
        self.archive.addfile(entry)

    def content(self, name: str, data: bytes) -> None:
        self._count(len(data))
        entry = tarfile.TarInfo(name)
        entry.size = len(data)
        entry.mode = 0o600
        entry.mtime = int(time.time())
        self.archive.addfile(entry, io.BytesIO(data))

    def regular_file(self, source: Path, name: str) -> None:
        if source.is_symlink():
            raise ValueError("Refusing symlinked backup content")
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(source, flags)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode):
                raise ValueError("Refusing non-regular backup content")
            self._count(info.st_size)
            entry = tarfile.TarInfo(name)
            entry.size = info.st_size
            entry.mode = 0o600
            entry.mtime = int(info.st_mtime)
            self.archive.addfile(entry, stream)

    def sqlite_database(self, source: Path, name: str) -> None:
        if source.is_symlink() or not source.is_file():
            raise ValueError("Refusing symlinked or invalid SQLite database")
        uri = "file:" + quote(source.resolve().as_posix(), safe="/:") + "?mode=ro"
        with sqlite3.connect(uri, uri=True, timeout=5) as live:
            # Check before allocating the memory snapshot; the authoritative
            # limit is checked again after serialize().
            page_size = int(live.execute("PRAGMA page_size").fetchone()[0])
            page_count = int(live.execute("PRAGMA page_count").fetchone()[0])
            if page_size * page_count > _MAX_SQLITE_MEMORY:
                raise ValueError("Database too large for memory-safe encrypted export")
            with sqlite3.connect(":memory:") as snapshot:
                live.backup(snapshot)
                data = snapshot.serialize()
        if len(data) > _MAX_SQLITE_MEMORY:
            raise ValueError("Database too large for memory-safe encrypted export")
        self.content(name, data)

    def tree(self, root: Path, label: str, *, excluded: frozenset[str] = frozenset()):
        if root.is_symlink():
            raise ValueError("Refusing symlinked recovery root")
        if not root.exists():
            return
        if not root.is_dir():
            raise ValueError("Recovery root is not a directory")
        self.directory(label)
        for folder, dirs, files in os.walk(root, followlinks=False):
            relative = Path(folder).relative_to(root)
            dirs[:] = sorted(name for name in dirs
                             if relative.parts or name not in excluded)
            for dirname in dirs:
                item = Path(folder) / dirname
                if item.is_symlink():
                    raise ValueError("Refusing symlinked backup directory")
                member = (Path(label) / relative / dirname).as_posix()
                self.directory(member)
            for filename in sorted(files):
                if not relative.parts and filename in excluded:
                    continue
                item = Path(folder) / filename
                member = (Path(label) / relative / filename).as_posix()
                if not relative.parts and filename == "jervis.sqlite3" and label == "data":
                    self.sqlite_database(item, member)
                else:
                    self.regular_file(item, member)


def create_streamed_encrypted_backup(destination: Path, passphrase: str,
                                     *, paths: Paths | None = None) -> Path:
    """Publish an encrypted JERVIS-ENC-BACKUP-v1 without plaintext disk staging."""
    from .encrypted_backup import (
        MAGIC, SALT_SIZE, NONCE_SIZE, _cipher, _derive_key,
    )

    resolved = paths or Paths.resolve()
    dst = Path(destination).expanduser().absolute()
    if dst.exists() or dst.is_symlink():
        raise FileExistsError("Refusing to overwrite existing encrypted backup")
    # Validate credentials before reading or staging any private state.
    salt = os.urandom(SALT_SIZE)
    nonce = os.urandom(NONCE_SIZE)
    key = _derive_key(passphrase, salt)
    header = MAGIC + salt + nonce
    resolved.ensure()
    dst.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
    identifier = stamp + "-encrypted-export-" + secrets.token_hex(3)
    metadata = {
        "id": identifier,
        "created_at": time.time(),
        "reason": "encrypted-export",
        "version": __version__,
        "archive": str(dst),
        "includes_binary": False,
    }

    temporary = None
    try:
        fd, name = tempfile.mkstemp(prefix=".jervis-enc-", dir=dst.parent)
        temporary = Path(name)
        with os.fdopen(fd, "wb") as output:
            output.write(header)
            worker = _cipher(key, nonce).encryptor()
            worker.authenticate_additional_data(header)
            sink = _EncryptedSink(output, worker)
            with tarfile.open(fileobj=sink, mode="w|gz") as archive:
                pack = _SnapshotPacker(archive)
                pack.content("snapshot.json", json.dumps(metadata, sort_keys=True).encode("utf-8"))
                pack.tree(resolved.config, "config")
                pack.tree(resolved.data, "data", excluded=frozenset({
                    "snapshots", "models", "tools", "jervis.sqlite3-wal",
                    "jervis.sqlite3-shm",
                }))
            output.write(worker.finalize())
            output.write(worker.tag)
            output.flush()
            os.fsync(output.fileno())
        # Atomic no-overwrite publication; no destination exists until success.
        os.link(temporary, dst)
        return dst
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
