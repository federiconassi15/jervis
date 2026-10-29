"""Signed plugin installation is opt-in and never executes plugin contents."""
import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from jervis.plugin_marketplace import install_signed_manifest
from jervis.plugin_engine import invoke_static_plugin


def _material(extra=None):
    private = Ed25519PrivateKey.generate()
    key = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    payload = {
        "id": "demo.example", "version": "1.2.3", "publisher": "demo",
        "permissions": [], "description": "Demo static plugin",
        "commands": [{"name": "hello", "type": "response", "text": "Hello!"}],
    }
    if extra:
        payload.update(extra)
    raw = json.dumps(payload, separators=(",", ":")).encode()
    return private, key, raw


def test_signed_install_enforces_trust_and_consent(tmp_path):
    private, key, raw = _material()
    signature = private.sign(raw)
    with pytest.raises(PermissionError):
        install_signed_manifest(tmp_path, raw, signature,
                                trusted_publishers={"demo": key})
    with pytest.raises(PermissionError):
        install_signed_manifest(tmp_path, raw, signature,
                                trusted_publishers={}, consent=True)
    receipt = install_signed_manifest(tmp_path, raw, signature,
                                      trusted_publishers={"demo": key},
                                      consent=True)
    assert receipt.identifier == "demo.example"
    assert invoke_static_plugin(tmp_path, "demo.example", "hello") == "Hello!"
    with pytest.raises(FileExistsError):
        install_signed_manifest(tmp_path, raw, signature,
                                trusted_publishers={"demo": key}, consent=True)


def test_tampering_and_code_are_rejected(tmp_path):
    private, key, raw = _material()
    signature = private.sign(raw)
    with pytest.raises(ValueError, match="signature"):
        install_signed_manifest(tmp_path, raw.replace(b"Hello!", b"HELLO!"), signature,
                                trusted_publishers={"demo": key}, consent=True)
    private, key, raw = _material({
        "commands": [{"name": "pwn", "type": "python", "text": "print(1)"}],
    })
    with pytest.raises(ValueError, match="static"):
        install_signed_manifest(tmp_path, raw, private.sign(raw),
                                trusted_publishers={"demo": key}, consent=True)
    private, key, raw = _material({"permissions": ["filesystem.write"]})
    with pytest.raises(ValueError, match="zero-capability"):
        install_signed_manifest(tmp_path, raw, private.sign(raw),
                                trusted_publishers={"demo": key}, consent=True)


def test_invalid_manifest_paths_and_symlinks(tmp_path):
    private, key, raw = _material({"id": "../../outside"})
    with pytest.raises(ValueError, match="identifier"):
        install_signed_manifest(tmp_path, raw, private.sign(raw),
                                trusted_publishers={"demo": key}, consent=True)
    private, key, raw = _material()
    target = tmp_path / "actual"
    target.mkdir()
    link = tmp_path / "link"
    try:
        link.symlink_to(target, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks unavailable")
    with pytest.raises(PermissionError):
        install_signed_manifest(link, raw, private.sign(raw),
                                trusted_publishers={"demo": key}, consent=True)
