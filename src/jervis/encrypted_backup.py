"""Authenticated encrypted backup exports for Jervis 8.1.

Format: MAGIC | 16-byte random salt | 12-byte random GCM nonce |
        AES-256-GCM encrypted tar.gz payload | 16-byte authentication tag.

The exported archive is encrypted, not existing local recovery snapshots.
No password, derived key, plaintext backup or sensitive path is logged.
"""
from __future__ import annotations

import os
import re
import shutil
import tempfile
import tarfile
from pathlib import Path, PurePosixPath

from .paths import Paths

MAGIC = b"JERVIS-ENC-BACKUP-v1\n"
SALT_SIZE = 16
NONCE_SIZE = 12
TAG_SIZE = 16
_CHUNK = 1024 * 1024
_MAX_ARCHIVE = 1024 * 1024 * 1024 * 2
_MAX_MEMBERS = 12000


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

    if not isinstance(passphrase, str) or len(passphrase) < 12:
        raise ValueError("Backup passphrase must contain at least 12 characters")
    return Scrypt(salt=salt, length=32, n=2**15, r=8, p=1).derive(
        passphrase.encode("utf-8")
    )


def _cipher(key: bytes, nonce: bytes, tag: bytes | None = None):
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    return Cipher(algorithms.AES(key), modes.GCM(nonce, tag))


def encrypt_file(source: Path, destination: Path, passphrase: str) -> Path:
    """Stream and atomically publish a private authenticated archive."""
    src = Path(source)
    dst = Path(destination).expanduser().absolute()
    if src.resolve() == dst.resolve():
        raise ValueError("Source and encrypted destination must differ")
    if dst.exists() or dst.is_symlink():
        raise FileExistsError("Refusing to overwrite an existing backup")
    if not src.is_file() or src.is_symlink():
        raise ValueError("Backup source is not a regular file")
    if src.stat().st_size > _MAX_ARCHIVE:
        raise ValueError("Backup exceeds the safe 2 GiB size bound")
    salt = os.urandom(SALT_SIZE)
    nonce = os.urandom(NONCE_SIZE)
    key = _derive_key(passphrase, salt)
    header = MAGIC + salt + nonce
    destination_parent = dst.parent
    destination_parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temp: Path | None = None
    try:
        fd, temporary = tempfile.mkstemp(prefix=".jervis-enc-", dir=destination_parent)
        temp = Path(temporary)
        with os.fdopen(fd, "wb") as output, src.open("rb") as plain:
            output.write(header)
            worker = _cipher(key, nonce).encryptor()
            worker.authenticate_additional_data(header)
            while chunk := plain.read(_CHUNK):
                output.write(worker.update(chunk))
            output.write(worker.finalize())
            output.write(worker.tag)
            output.flush()
            os.fsync(output.fileno())
        if dst.exists() or dst.is_symlink():
            raise FileExistsError("Target appeared while writing backup")
        # Atomic link fails without altering any pre-existing destination,
        # unlike os.replace which could race with another writer.
        os.link(temp, dst)
        temp.unlink()
        temp = None
        return dst
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


def decrypt_file(source: Path, destination: Path, passphrase: str) -> Path:
    """Verify GCM authentication *before* making plaintext available."""
    from cryptography.exceptions import InvalidTag

    src = Path(source)
    dst = Path(destination)
    if src.resolve() == dst.resolve():
        raise ValueError("Source and destination must differ")
    if dst.exists() or dst.is_symlink():
        raise FileExistsError("Refusing to overwrite decrypted destination")
    if not src.is_file() or src.is_symlink():
        raise ValueError("Encrypted backup is not a regular file")
    total = src.stat().st_size
    header_size = len(MAGIC) + SALT_SIZE + NONCE_SIZE
    if total < header_size + TAG_SIZE or total > _MAX_ARCHIVE + header_size + TAG_SIZE:
        raise ValueError("Invalid encrypted backup size")
    with src.open("rb") as handle:
        header = handle.read(header_size)
        if not header.startswith(MAGIC):
            raise ValueError("Unknown encrypted backup format")
        salt = header[len(MAGIC):len(MAGIC) + SALT_SIZE]
        nonce = header[-NONCE_SIZE:]
        key = _derive_key(passphrase, salt)
        handle.seek(total - TAG_SIZE)
        tag = handle.read(TAG_SIZE)
        handle.seek(header_size)
        worker = _cipher(key, nonce, tag).decryptor()
        worker.authenticate_additional_data(header)
        dst.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        try:
            # Mode 0600; callers must use a private staging directory.
            fd = os.open(dst, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as output:
                remaining = total - header_size - TAG_SIZE
                while remaining:
                    chunk = handle.read(min(_CHUNK, remaining))
                    if not chunk:
                        raise ValueError("Encrypted backup truncated")
                    remaining -= len(chunk)
                    output.write(worker.update(chunk))
                try:
                    output.write(worker.finalize())
                except InvalidTag as exc:
                    raise ValueError("Incorrect passphrase or corrupted backup") from exc
            return dst
        except BaseException:
            dst.unlink(missing_ok=True)
            raise


def _verify_restorable_archive(path: Path) -> str:
    """Validate members before passing imported tar to legacy restore_snapshot."""
    import json
    size = 0
    seen = set()
    identifier = ""
    with tarfile.open(path, "r:gz") as archive:
        for index, member in enumerate(archive):
            if index >= _MAX_MEMBERS:
                raise ValueError("Too many backup members")
            name = member.name
            parsed = PurePosixPath(name)
            if (not name or name.startswith("/") or "\\" in name or
                    ":" in name or ".." in parsed.parts or name in seen or
                    not (member.isfile() or member.isdir())):
                raise ValueError("Unsafe backup archive member")
            seen.add(name)
            if not member.isfile():
                continue
            size += member.size
            if member.size < 0 or size > _MAX_ARCHIVE:
                raise ValueError("Backup archive too large")
            data = archive.extractfile(member)
            if data is None:
                raise ValueError("Missing backup archive entry")
            with data:
                if name == "snapshot.json":
                    if member.size > 16384:
                        raise ValueError("Backup metadata too large")
                    info = json.loads(data.read())
                    identifier = info["id"]
                    if not isinstance(identifier, str) or not re.fullmatch(
                        r"[0-9]{8}-[0-9]{6}-[a-z0-9_-]{1,48}", identifier
                    ):
                        raise ValueError("Invalid snapshot identifier")
                    for field in ("created_at", "reason", "version", "archive",
                                  "includes_binary"):
                        if field not in info:
                            raise ValueError("Backup metadata incomplete")
                else:
                    while data.read(_CHUNK):
                        pass
    if not identifier:
        raise ValueError("Missing snapshot metadata")
    return identifier


def create_encrypted_backup(destination: Path, passphrase: str,
                            *, paths: Paths | None = None) -> Path:
    """Produce a compatible authenticated archive without plaintext disk staging."""
    from .secure_export import create_streamed_encrypted_backup

    return create_streamed_encrypted_backup(destination, passphrase, paths=paths)


def restore_encrypted_backup(source: Path, passphrase: str,
                             *, paths: Paths | None = None) -> str:
    """Authenticate before touching Jervis state. Snapshot guard remains plaintext."""
    from .snapshots import restore_snapshot

    resolved = paths or Paths.resolve()
    resolved.ensure()
    resolved.cache.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="jervis-unseal-", dir=resolved.cache) as root:
        staging = Path(root)
        decrypted = decrypt_file(source, staging / "plain.tar.gz", passphrase)
        identifier = _verify_restorable_archive(decrypted)
        snapshots = resolved.data / "snapshots"
        snapshots.mkdir(mode=0o700, parents=True, exist_ok=True)
        destination = snapshots / (identifier + ".tar.gz")
        # The exclusive open is the *publication* operation. A separate
        # exists()/copy2() check races with legitimate concurrent restorers.
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(destination, flags, 0o600)
        owned_identity = None
        try:
            with os.fdopen(fd, "wb") as target, decrypted.open("rb") as plain:
                shutil.copyfileobj(plain, target, _CHUNK)
                target.flush()
                os.fsync(target.fileno())
                owned_identity = os.fstat(target.fileno())
            restore_snapshot(identifier, paths=resolved, make_guard=True,
                             restore_binary=False)
            return identifier
        finally:
            # Never unlink a different snapshot that appeared at this name
            # after our restore, including during an exception or rollback.
            try:
                current = destination.lstat()
            except FileNotFoundError:
                pass
            else:
                if (owned_identity is not None
                        and not destination.is_symlink()
                        and current.st_dev == owned_identity.st_dev
                        and current.st_ino == owned_identity.st_ino
                        and current.st_ctime_ns == owned_identity.st_ctime_ns
                        and current.st_size == owned_identity.st_size):
                    destination.unlink(missing_ok=True)
