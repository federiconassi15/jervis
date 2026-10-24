"""AES-GCM archive confidentiality, tamper rejection and atomicity tests."""
import os
from pathlib import Path

import pytest

from jervis.encrypted_backup import decrypt_file, encrypt_file, MAGIC


def test_roundtrip_does_not_contain_plaintext(tmp_path):
    source = tmp_path / "plain"
    source.write_bytes((b"SECRET-JERVIS-VOICE-DATA-" * 1024) + os.urandom(100))
    encrypted = tmp_path / "archive.jenc"
    encrypt_file(source, encrypted, "correct horse battery staple")
    assert encrypted.read_bytes().startswith(MAGIC)
    assert b"SECRET-JERVIS-VOICE-DATA" not in encrypted.read_bytes()
    restored = tmp_path / "restored"
    decrypt_file(encrypted, restored, "correct horse battery staple")
    assert restored.read_bytes() == source.read_bytes()
    if os.name != "nt":
        assert restored.stat().st_mode & 0o077 == 0


def test_wrong_password_and_tag_tamper_leave_no_plaintext(tmp_path):
    origin = tmp_path / "origin"
    origin.write_bytes(os.urandom(1024))
    enc = tmp_path / "enc"
    encrypt_file(origin, enc, "correct horse battery staple")
    with pytest.raises(ValueError):
        decrypt_file(enc, tmp_path / "wrong", "completely wrong passphrase")
    assert not (tmp_path / "wrong").exists()
    tampered = bytearray(enc.read_bytes())
    tampered[-20] ^= 1
    enc.write_bytes(tampered)
    with pytest.raises(ValueError):
        decrypt_file(enc, tmp_path / "tampered", "correct horse battery staple")
    assert not (tmp_path / "tampered").exists()


def test_short_passphrase_and_refusal_to_overwrite(tmp_path):
    origin = tmp_path / "plain"
    origin.write_bytes(b"safe data")
    with pytest.raises(ValueError):
        encrypt_file(origin, tmp_path / "encrypted", "short")
    output = tmp_path / "encrypted"
    encrypt_file(origin, output, "a long strong passphrase")
    with pytest.raises(FileExistsError):
        encrypt_file(origin, output, "a long strong passphrase")
    with pytest.raises(FileExistsError):
        decrypt_file(output, origin, "a long strong passphrase")


def test_plain_file_not_accepted(tmp_path):
    source = tmp_path / "random.bin"
    source.write_bytes(os.urandom(200))
    with pytest.raises(ValueError, match="format"):
        decrypt_file(source, tmp_path / "out", "correct horse battery staple")
    assert not (tmp_path / "out").exists()
