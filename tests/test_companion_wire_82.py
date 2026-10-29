"""Relay transport cannot bypass channel authentication."""
import pytest

from jervis.companion_crypto import generate_identity, public_der, derive_channel
from jervis.companion_wire import pack_ciphertext, unpack_ciphertext


def test_encrypted_host_to_phone_through_opaque_relay():
    h = generate_identity()
    p = generate_identity()
    host = derive_channel(
        h, role="host", instance_id="a"*32, device_id="b"*32,
        session_id="c"*32, host_ephemeral=public_der(h),
        phone_ephemeral=public_der(p),
    )
    phone = derive_channel(
        p, role="phone", instance_id="a"*32, device_id="b"*32,
        session_id="c"*32, host_ephemeral=public_der(h),
        phone_ephemeral=public_der(p),
    )
    ciphertext = host.encrypt(b"private hello")
    frame = pack_ciphertext(ciphertext)
    assert frame["kind"] == "ciphertext"
    assert frame["body"] != "private hello"
    decoded = unpack_ciphertext(frame)
    assert phone.decrypt(decoded) == b"private hello"
    with pytest.raises(ValueError, match="replayed"):
        phone.decrypt(unpack_ciphertext(frame))


def test_outer_frame_tampering_and_plain_commands_rejected():
    valid = {"v":1, "session":"c"*32, "direction":"host",
             "seq":0, "body":"abcDEF012_-"}
    frame = pack_ciphertext(valid)
    with pytest.raises(ValueError):
        pack_ciphertext({"command": "shutdown"})
    wrong = dict(frame, seq=2)
    with pytest.raises(ValueError, match="does not match"):
        unpack_ciphertext(wrong)
    wrong = dict(frame, kind="command")
    with pytest.raises(ValueError):
        unpack_ciphertext(wrong)
