"""Consent-gated, in-memory image intake for Jervis Vision 8.2.

No screenshot capture, OCR, cloud upload, model invocation, hidden camera access,
disk persistence, or raw image logging happens here. User selects an actual
local image, authorizes that exact path, and the bytes stay in process memory.
"""
from __future__ import annotations

import hashlib
import os
import stat
import struct
from dataclasses import dataclass
from pathlib import Path

from .capabilities import CapabilityGrant, Principal, authorize

_MAX_BYTES = 8 * 1024 * 1024
_MAX_PIXELS = 20_000_000
_MAX_EDGE = 8192


@dataclass(frozen=True)
class ImageArtifact:
    mime_type: str
    width: int
    height: int
    sha256: str
    content: bytes


def _dimensions_png(data: bytes) -> tuple[int, int]:
    if len(data) < 33 or not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Unknown PNG header")
    if data[12:16] != b"IHDR" or struct.unpack(">I", data[8:12])[0] != 13:
        raise ValueError("Missing PNG dimensions")
    return struct.unpack(">II", data[16:24])


def _dimensions_jpeg(data: bytes) -> tuple[int, int]:
    if not data.startswith(b"\xff\xd8"):
        raise ValueError("Unknown JPEG header")
    position = 2
    while position + 4 < min(len(data), 65536):
        if data[position] != 0xff:
            raise ValueError("Malformed JPEG segment marker")
        while position < len(data) and data[position] == 0xff:
            position += 1
        if position >= len(data):
            break
        marker = data[position]
        position += 1
        if marker in {0xd8, 0xd9, 0x01} or 0xd0 <= marker <= 0xd7:
            continue
        if marker == 0xda:  # Start of scan reached without SOF
            break
        if position + 2 > len(data):
            break
        size = struct.unpack(">H", data[position:position + 2])[0]
        if size < 2 or position + size > len(data):
            raise ValueError("Malformed JPEG marker length")
        if marker in {0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7,
                      0xc9, 0xca, 0xcb, 0xcd, 0xce, 0xcf}:
            if size < 7:
                raise ValueError("Invalid JPEG dimensions")
            height, width = struct.unpack(">HH", data[position + 3:position + 7])
            return width, height
        position += size
    raise ValueError("No valid JPEG dimensions found")


def inspect_selected_image(path: Path, principal: Principal, *,
                           grants: tuple[CapabilityGrant, ...] = (),
                           consent: bool = False) -> ImageArtifact:
    """Read the explicitly selected path, without storing or uploading contents."""
    if not consent:
        raise PermissionError("Explicit image inspection consent required")
    target = Path(path).expanduser()
    if target.is_symlink() or not target.is_file():
        raise ValueError("Only regular, non-symlinked images may be read")
    actual = target.resolve(strict=True)
    decision = authorize(
        principal, "filesystem.read", scope=str(actual), grants=grants
    )
    if not decision.permitted:
        raise PermissionError(decision.reason)
    if target.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
        raise ValueError("Only PNG and JPEG images are supported")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(target, flags)
    with os.fdopen(descriptor, "rb") as image:
        info = os.fstat(image.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("Image is not a regular file")
        if not 32 <= info.st_size <= _MAX_BYTES:
            raise ValueError("Image exceeds configured size limits")
        data = image.read(_MAX_BYTES + 1)
    if len(data) != info.st_size:
        raise ValueError("Image changed while being read")
    if target.suffix.lower() == ".png":
        width, height = _dimensions_png(data)
        mime = "image/png"
    else:
        width, height = _dimensions_jpeg(data)
        mime = "image/jpeg"
    if not 1 <= width <= _MAX_EDGE or not 1 <= height <= _MAX_EDGE:
        raise ValueError("Image dimensions exceed safe bounds")
    if width * height > _MAX_PIXELS:
        raise ValueError("Image pixel budget exceeded")
    return ImageArtifact(
        mime, width, height, hashlib.sha256(data).hexdigest(), data
    )
