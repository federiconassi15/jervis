"""Opt-in signed installation of declarative-only Jervis plugins.

A valid signature proves origin, NOT safety or permission. Only a known,
out-of-band pinned publisher key can be used; executable plugin code, dynamic
dependencies and non-static commands are rejected. There is no network fetch.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

_ID = re.compile(r"[a-z0-9][a-z0-9.-]{0,63}\Z")
_PUBLISHER = re.compile(r"[a-z][a-z0-9_.-]{0,63}\Z")
_VERSION = re.compile(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)\Z")
_COMMAND = re.compile(r"[a-z][a-z0-9_-]{0,47}\Z")
_MAX_MANIFEST_BYTES = 16384


@dataclass(frozen=True)
class InstallReceipt:
    identifier: str
    version: str
    publisher: str
    path: Path


def _validate_manifest(raw: bytes) -> dict:
    if not isinstance(raw, bytes) or len(raw) > _MAX_MANIFEST_BYTES or not raw:
        raise ValueError("Invalid manifest size")
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Manifest must be an object")
    if not _ID.fullmatch(str(data.get("id", ""))):
        raise ValueError("Invalid plugin identifier")
    if not _VERSION.fullmatch(str(data.get("version", ""))):
        raise ValueError("Invalid semantic version")
    if not _PUBLISHER.fullmatch(str(data.get("publisher", ""))):
        raise ValueError("Invalid publisher identifier")
    if data.get("permissions") != []:
        raise ValueError("Marketplace only permits zero-capability static plugins")
    commands = data.get("commands")
    if not isinstance(commands, list) or not 1 <= len(commands) <= 32:
        raise ValueError("Invalid plugin commands")
    if not isinstance(data.get("description", ""), str):
        raise ValueError("Invalid plugin description")
    seen = set()
    for row in commands:
        if not isinstance(row, dict) or set(row) != {"name", "type", "text"}:
            raise ValueError("Plugin commands must be static responses")
        name = row["name"]
        text = row["text"]
        if (not isinstance(name, str) or not _COMMAND.fullmatch(name)
                or name in seen or row["type"] != "response"
                or not isinstance(text, str) or not 1 <= len(text) <= 360
                or "\x00" in text):
            raise ValueError("Invalid static plugin command")
        seen.add(name)
    # Reject unknown script/config keys. No hidden runtime side channels.
    permitted = {"id", "version", "publisher", "permissions", "description", "commands"}
    if set(data) - permitted:
        raise ValueError("Unsupported manifest properties")
    return data


def install_signed_manifest(root: Path, raw_manifest: bytes, signature: bytes, *,
                            trusted_publishers: dict[str, bytes],
                            consent: bool = False) -> InstallReceipt:
    if not consent:
        raise PermissionError("Explicit owner installation consent required")
    if not isinstance(signature, bytes) or len(signature) != 64:
        raise ValueError("Invalid Ed25519 signature")
    manifest = _validate_manifest(raw_manifest)
    publisher = manifest["publisher"]
    public_key = trusted_publishers.get(publisher)
    if not isinstance(public_key, bytes) or len(public_key) != 32:
        raise PermissionError("Publisher is not in the out-of-band trust store")
    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(signature, raw_manifest)
    except (InvalidSignature, ValueError) as exc:
        raise ValueError("Manifest signature verification failed") from exc
    root = Path(root)
    if root.is_symlink():
        raise PermissionError("Cannot install to a symlinked plugin directory")
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    destination = root / manifest["id"]
    # Exact exclusive directory creation; never overwrite an installed plugin.
    destination.mkdir(mode=0o700, exist_ok=False)
    try:
        target = destination / "plugin.json"
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(target, flags, 0o600)
        with os.fdopen(descriptor, "wb") as out:
            out.write(raw_manifest)
            out.flush()
            os.fsync(out.fileno())
    except BaseException:
        try:
            (destination / "plugin.json").unlink(missing_ok=True)
            destination.rmdir()
        except OSError:
            pass
        raise
    return InstallReceipt(manifest["id"], manifest["version"],
                          publisher, destination)
