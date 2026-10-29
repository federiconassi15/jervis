"""Local image consent and privacy boundaries for the 8.2 vision intake."""
import struct
import pytest

from jervis.capabilities import CapabilityGrant, Principal
from jervis.vision_intake import inspect_selected_image


def _png(width=128, height=80):
    # Header inspection only: not a complete decoded PNG image.
    return (b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR"
            + struct.pack(">II", width, height) + bytes((8, 6, 0, 0, 0))
            + bytes(4))


def test_selected_image_needs_consent_and_exact_scoped_read(tmp_path):
    image = tmp_path / "private.png"
    image.write_bytes(_png())
    owner = Principal("owner", "owner", True)
    grant = CapabilityGrant("owner", "filesystem.read", str(image.resolve()), 10**12)
    with pytest.raises(PermissionError):
        inspect_selected_image(image, owner, grants=(grant,))
    with pytest.raises(PermissionError):
        inspect_selected_image(image, owner, consent=True)
    item = inspect_selected_image(image, owner, grants=(grant,), consent=True)
    assert item.mime_type == "image/png"
    assert (item.width, item.height) == (128, 80)
    assert item.sha256 and item.content == image.read_bytes()
    remote = Principal("owner", "owner", True, "phone")
    with pytest.raises(PermissionError):
        inspect_selected_image(image, remote, grants=(grant,), consent=True)


def test_reject_symlink_and_decompression_bomb_dimensions(tmp_path):
    target = tmp_path / "outside.png"
    target.write_bytes(_png())
    link = tmp_path / "linked.png"
    try:
        link.symlink_to(target)
    except (NotImplementedError, OSError):
        pytest.skip("Symlinks unavailable")
    principal = Principal("owner", "owner", True)
    grant = CapabilityGrant("owner", "filesystem.read", str(tmp_path.resolve()), 10**12)
    with pytest.raises(ValueError, match="non-symlinked"):
        inspect_selected_image(link, principal, grants=(grant,), consent=True)
    bomb = tmp_path / "bomb.png"
    bomb.write_bytes(_png(100000, 100000))
    with pytest.raises(ValueError, match="dimensions"):
        inspect_selected_image(bomb, principal, grants=(grant,), consent=True)


def test_reject_unknown_formats_and_unscoped_files(tmp_path):
    principal = Principal("owner", "owner", True)
    file = tmp_path / "image.png"
    file.write_bytes(b"not actually a PNG image" * 3)
    grant = CapabilityGrant("owner", "filesystem.read", str(file.resolve()), 10**12)
    with pytest.raises(ValueError):
        inspect_selected_image(file, principal, grants=(grant,), consent=True)
    unknown = tmp_path / "image.webp"
    unknown.write_bytes(bytes(128))
    other_grant = CapabilityGrant(
        "owner", "filesystem.read", str(unknown.resolve()), 10**12,
    )
    with pytest.raises(ValueError):
        inspect_selected_image(unknown, principal, grants=(other_grant,), consent=True)
