"""Authenticated P-256 handshake, cross-role encryption and replay protection."""
import pytest
from cryptography.exceptions import InvalidSignature, InvalidTag

from jervis.companion_crypto import (
    generate_identity, public_der, sign_host, verify_host, sign_phone,
    verify_phone, derive_channel,
)

INSTANCE = "a" * 32
DEVICE = "b" * 32
SESSION = "c" * 32


def _pair():
    host_identity = generate_identity()
    phone_identity = generate_identity()
    phone_ephemeral = generate_identity()
    host_ephemeral = generate_identity()
    phone_der = public_der(phone_ephemeral)
    host_der = public_der(host_ephemeral)
    phone_sig = sign_phone(
        phone_identity, instance_id=INSTANCE, device_id=DEVICE,
        session_id=SESSION, phone_ephemeral=phone_der,
    )
    verify_phone(public_der(phone_identity), phone_sig,
                 instance_id=INSTANCE, device_id=DEVICE,
                 session_id=SESSION, phone_ephemeral=phone_der)
    host_sig = sign_host(host_identity,
                         instance_id=INSTANCE, device_id=DEVICE,
                         session_id=SESSION, phone_ephemeral=phone_der,
                         host_ephemeral=host_der)
    verify_host(public_der(host_identity), host_sig,
                instance_id=INSTANCE, device_id=DEVICE,
                session_id=SESSION, phone_ephemeral=phone_der,
                host_ephemeral=host_der)
    phone = derive_channel(phone_ephemeral, role="phone",
                            instance_id=INSTANCE, device_id=DEVICE,
                            session_id=SESSION, phone_ephemeral=phone_der,
                            host_ephemeral=host_der)
    host = derive_channel(host_ephemeral, role="host",
                           instance_id=INSTANCE, device_id=DEVICE,
                           session_id=SESSION, phone_ephemeral=phone_der,
                           host_ephemeral=host_der)
    return host, phone, host_identity, phone_der, host_der, host_sig


def test_authenticated_two_way_messages_and_replay_rejection():
    host, phone, *_ = _pair()
    message = host.encrypt(b"Hello from Jervis")
    assert phone.decrypt(message) == b"Hello from Jervis"
    with pytest.raises(ValueError, match="replayed"):
        phone.decrypt(message)
    reply = phone.encrypt(b"Phone is connected")
    assert host.decrypt(reply) == b"Phone is connected"


def test_wrong_identity_handshake_is_rejected():
    host, phone, identity, phone_der, host_der, sig = _pair()
    with pytest.raises(InvalidSignature):
        verify_host(public_der(generate_identity()), sig,
                    instance_id=INSTANCE, device_id=DEVICE,
                    session_id=SESSION, phone_ephemeral=phone_der,
                    host_ephemeral=host_der)
    with pytest.raises(InvalidSignature):
        verify_host(public_der(identity), sig,
                    instance_id=INSTANCE, device_id="d" * 32,
                    session_id=SESSION, phone_ephemeral=phone_der,
                    host_ephemeral=host_der)


def test_tampering_wrong_direction_and_sequence_rejected():
    host, phone, *_ = _pair()
    message = host.encrypt(b"Private, authenticated ciphertext")
    forged = dict(message)
    forged["body"] = ("A" if message["body"][0] != "A" else "B") + message["body"][1:]
    with pytest.raises(InvalidTag):
        phone.decrypt(forged)
    assert phone.decrypt(message) == b"Private, authenticated ciphertext"
    with pytest.raises(ValueError):
        host.decrypt(message)
    wrong_session = dict(phone.encrypt(b"test"))
    wrong_session["session"] = "0" * 32
    with pytest.raises(ValueError):
        host.decrypt(wrong_session)


def test_message_size_and_session_boundaries():
    host, phone, *_ = _pair()
    with pytest.raises(ValueError):
        host.encrypt(b"x" * 32769)
    with pytest.raises(ValueError):
        host.encrypt("not bytes")
    with pytest.raises(ValueError):
        derive_channel(generate_identity(), role="host",
                       instance_id=INSTANCE, device_id=DEVICE,
                       session_id=SESSION, phone_ephemeral=public_der(generate_identity()),
                       host_ephemeral=public_der(generate_identity()))
