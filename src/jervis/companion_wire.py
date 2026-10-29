"""Opaque relay framing for authenticated encrypted companion envelopes.

The relay frame is only transport. The underlying SecureChannel still verifies
session, direction, sequence, authentication tag and replay protection.
"""
from __future__ import annotations

import base64
import json
import re
import uuid

_MAX_INNER = 45500
_MAX_OUTER = 65536
_ID = re.compile(r"[0-9a-f]{32}\Z")
_TEXT = re.compile(r"[A-Za-z0-9_-]{1,45000}\Z")


def _valid_envelope(envelope: dict) -> bool:
    return (
        isinstance(envelope, dict)
        and set(envelope) == {"v", "session", "direction", "seq", "body"}
        and envelope.get("v") == 1
        and isinstance(envelope.get("session"), str)
        and bool(_ID.fullmatch(envelope["session"]))
        and envelope.get("direction") in {"host", "phone"}
        and type(envelope.get("seq")) is int
        and 0 <= envelope["seq"] <= (1 << 53) - 1
        and isinstance(envelope.get("body"), str)
        and bool(_TEXT.fullmatch(envelope["body"]))
    )


def pack_ciphertext(envelope: dict) -> dict:
    """Package a SecureChannel.encrypted payload for the Cloudflare relay."""
    if not _valid_envelope(envelope):
        raise ValueError("Invalid authenticated channel envelope")
    raw = json.dumps(envelope, separators=(",", ":"), sort_keys=True).encode("ascii")
    if len(raw) > _MAX_INNER:
        raise ValueError("Encrypted envelope too large")
    body = base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")
    if len(body) > _MAX_OUTER:
        raise ValueError("Relay frame too large")
    return {
        "v": 1, "kind": "ciphertext", "id": uuid.uuid4().hex,
        "seq": envelope["seq"], "body": body,
    }


def unpack_ciphertext(frame: dict) -> dict:
    """Decode transport framing, not an authorization or decryption operation."""
    if not isinstance(frame, dict) or set(frame) != {
        "v", "kind", "id", "seq", "body"
    } or frame.get("v") != 1 or frame.get("kind") != "ciphertext":
        raise ValueError("Invalid ciphertext frame")
    if not isinstance(frame.get("id"), str) or not _ID.fullmatch(frame["id"]):
        raise ValueError("Invalid frame ID")
    if type(frame.get("seq")) is not int or not 0 <= frame["seq"] <= (1 << 53) - 1:
        raise ValueError("Invalid frame sequence")
    body = frame.get("body")
    if not isinstance(body, str) or not re.fullmatch(
        r"[A-Za-z0-9_-]{1,65536}", body
    ):
        raise ValueError("Invalid opaque frame body")
    try:
        raw = base64.b64decode(
            body + "=" * (-len(body) % 4), altchars=b"-_", validate=True
        )
        if len(raw) > _MAX_INNER:
            raise ValueError("Encrypted envelope too large")
        envelope = json.loads(raw)
    except (ValueError, UnicodeDecodeError, TypeError) as exc:
        raise ValueError("Malformed encrypted channel envelope") from exc
    if not _valid_envelope(envelope) or frame["seq"] != envelope["seq"]:
        raise ValueError("Untrusted relay frame does not match encrypted envelope")
    return envelope
