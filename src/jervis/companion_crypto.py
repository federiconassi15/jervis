"""Authenticated ephemeral P-256 secure session primitives for Jervis 8.2.

The relay sees ciphertext only. Host/phone identity keys must be independently
pinned after explicit physical pairing; this module never creates permissions,
makes network connections, or runs remotely requested actions.
"""
from __future__ import annotations

import base64
import hashlib
import os
import struct
from dataclasses import dataclass

from cryptography.exceptions import InvalidSignature, InvalidTag
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

_CONTEXT = b"JERVIS-COMPANION-E2E-V1"
_MAX_CONTENT = 32768
_MAX_SEQUENCE = (1 << 53) - 1


def generate_identity() -> ec.EllipticCurvePrivateKey:
    return ec.generate_private_key(ec.SECP256R1())


def public_der(key: ec.EllipticCurvePrivateKey) -> bytes:
    if not isinstance(key.curve, ec.SECP256R1):
        raise ValueError("Expected NIST P-256 identity")
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )


def _public(value: bytes) -> ec.EllipticCurvePublicKey:
    if not isinstance(value, bytes) or len(value) > 256:
        raise ValueError("Invalid public key")
    obj = serialization.load_der_public_key(value)
    if not isinstance(obj, ec.EllipticCurvePublicKey) or not isinstance(
        obj.curve, ec.SECP256R1
    ):
        raise ValueError("Only P-256 identity keys are supported")
    # Canonical encoding avoids aliases in the signed transcript.
    if obj.public_bytes(serialization.Encoding.DER,
                        serialization.PublicFormat.SubjectPublicKeyInfo) != value:
        raise ValueError("Noncanonical public key")
    return obj


def _identifiers(instance_id: str, device_id: str, session_id: str) -> tuple[bytes, ...]:
    ids = (instance_id, device_id, session_id)
    if any(not isinstance(value, str) or len(value) != 32 or
           any(char not in "0123456789abcdef" for char in value) for value in ids):
        raise ValueError("Identity and session IDs must be 128-bit lowercase hex")
    return tuple(bytes.fromhex(value) for value in ids)


def _transcript(kind: bytes, instance_id: str, device_id: str, session_id: str,
                phone_ephemeral: bytes, host_ephemeral: bytes = b"") -> bytes:
    instance, device, session = _identifiers(instance_id, device_id, session_id)
    parts = (_CONTEXT, kind, instance, device, session,
             phone_ephemeral, host_ephemeral)
    return b"".join(struct.pack(">H", len(item)) + item for item in parts)


def sign_phone(identity: ec.EllipticCurvePrivateKey, *,
               instance_id: str, device_id: str, session_id: str,
               phone_ephemeral: bytes) -> bytes:
    _public(phone_ephemeral)
    return identity.sign(_transcript(
        b"phone", instance_id, device_id, session_id, phone_ephemeral
    ), ec.ECDSA(hashes.SHA256()))


def verify_phone(pinned_phone_identity: bytes, signature: bytes, *,
                 instance_id: str, device_id: str, session_id: str,
                 phone_ephemeral: bytes) -> None:
    _public(phone_ephemeral)
    _public(pinned_phone_identity).verify(signature, _transcript(
        b"phone", instance_id, device_id, session_id, phone_ephemeral
    ), ec.ECDSA(hashes.SHA256()))


def sign_host(identity: ec.EllipticCurvePrivateKey, *,
              instance_id: str, device_id: str, session_id: str,
              phone_ephemeral: bytes, host_ephemeral: bytes) -> bytes:
    _public(phone_ephemeral)
    _public(host_ephemeral)
    return identity.sign(_transcript(
        b"host", instance_id, device_id, session_id, phone_ephemeral,
        host_ephemeral,
    ), ec.ECDSA(hashes.SHA256()))


def verify_host(pinned_host_identity: bytes, signature: bytes, *,
                instance_id: str, device_id: str, session_id: str,
                phone_ephemeral: bytes, host_ephemeral: bytes) -> None:
    _public(phone_ephemeral)
    _public(host_ephemeral)
    _public(pinned_host_identity).verify(signature, _transcript(
        b"host", instance_id, device_id, session_id,
        phone_ephemeral, host_ephemeral,
    ), ec.ECDSA(hashes.SHA256()))


@dataclass
class SecureChannel:
    """Strict monotonic receive sequence; replay is never accepted."""

    session_id: str
    direction: str
    send_key: bytes
    receive_key: bytes
    send_prefix: bytes
    receive_prefix: bytes
    next_send: int = 0
    last_received: int = -1

    def _aad(self, direction: str, seq: int) -> bytes:
        return _CONTEXT + bytes.fromhex(self.session_id) + direction.encode() + (
            seq.to_bytes(8, "big")
        )

    def encrypt(self, content: bytes) -> dict:
        if not isinstance(content, bytes) or len(content) > _MAX_CONTENT:
            raise ValueError("Message exceeds 32 KiB or is not bytes")
        if self.next_send > _MAX_SEQUENCE:
            raise OverflowError("Session sequence exhausted; rekey required")
        seq = self.next_send
        nonce = self.send_prefix + seq.to_bytes(8, "big")
        body = AESGCM(self.send_key).encrypt(nonce, content, self._aad(self.direction, seq))
        self.next_send += 1
        return {
            "v": 1, "session": self.session_id, "direction": self.direction,
            "seq": seq, "body": base64.urlsafe_b64encode(body).rstrip(b"=").decode(),
        }

    def decrypt(self, envelope: dict) -> bytes:
        if not isinstance(envelope, dict) or set(envelope) != {
            "v", "session", "direction", "seq", "body"
        }:
            raise ValueError("Invalid encrypted envelope")
        other = "phone" if self.direction == "host" else "host"
        seq = envelope["seq"]
        if (envelope["v"] != 1 or envelope["session"] != self.session_id
                or envelope["direction"] != other or type(seq) is not int
                or seq <= self.last_received or seq > _MAX_SEQUENCE):
            raise ValueError("Wrong session, direction or replayed sequence")
        body = envelope["body"]
        if not isinstance(body, str) or len(body) > 45000 or any(
            ch not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"
            for ch in body
        ):
            raise ValueError("Invalid encrypted message encoding")
        try:
            ciphertext = base64.urlsafe_b64decode(body + "=" * (-len(body) % 4))
        except (ValueError, base64.binascii.Error) as exc:
            raise ValueError("Invalid encrypted message") from exc
        if len(ciphertext) > _MAX_CONTENT + 16 or len(ciphertext) < 16:
            raise ValueError("Encrypted message size out of bounds")
        nonce = self.receive_prefix + seq.to_bytes(8, "big")
        # Update replay state only after authenticated decryption succeeds.
        result = AESGCM(self.receive_key).decrypt(nonce, ciphertext, self._aad(other, seq))
        self.last_received = seq
        return result


def derive_channel(our_ephemeral: ec.EllipticCurvePrivateKey, *,
                   role: str, instance_id: str, device_id: str, session_id: str,
                   phone_ephemeral: bytes, host_ephemeral: bytes) -> SecureChannel:
    if role not in {"host", "phone"}:
        raise ValueError("Unsupported channel role")
    own_der = public_der(our_ephemeral)
    expected = host_ephemeral if role == "host" else phone_ephemeral
    if own_der != expected:
        raise ValueError("Local ephemeral identity does not match transcript")
    peer = phone_ephemeral if role == "host" else host_ephemeral
    public = _public(peer)
    transcript = _transcript(
        b"keys", instance_id, device_id, session_id,
        phone_ephemeral, host_ephemeral,
    )
    shared = our_ephemeral.exchange(ec.ECDH(), public)
    material = HKDF(
        algorithm=hashes.SHA256(), length=72,
        salt=hashlib.sha256(transcript).digest(),
        info=_CONTEXT + b"/aes-gcm-key-material",
    ).derive(shared)
    host_to_phone = material[:32]
    phone_to_host = material[32:64]
    host_prefix = material[64:68]
    phone_prefix = material[68:72]
    if role == "host":
        return SecureChannel(session_id, role, host_to_phone, phone_to_host,
                             host_prefix, phone_prefix)
    return SecureChannel(session_id, role, phone_to_host, host_to_phone,
                         phone_prefix, host_prefix)
