#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
ARCHIVE = DIST / "jervis-installer.pyz"
CHECKSUM = DIST / "jervis-installer.pyz.sha256"
EXPECTED = {
    "__main__.py",
    "bootstrap.py",
    "pyproject.toml",
    "src/jervis/__init__.py",
    "src/jervis/version.py",
    "src/jervis/installer.py",
    "src/jervis/openclaw_setup.py",
    "src/jervis/prereqs.py",
}

if not ARCHIVE.is_file():
    raise SystemExit("release verification failed: jervis-installer.pyz is missing")

with zipfile.ZipFile(ARCHIVE) as bundle:
    names = set(bundle.namelist())
    missing = sorted(EXPECTED - names)
    if missing:
        raise SystemExit("release verification failed: missing " + ", ".join(missing))
    version_text = bundle.read("src/jervis/version.py").decode("utf-8")
    bootstrap_text = bundle.read("bootstrap.py").decode("utf-8")

version_match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', version_text)
bootstrap_match = re.search(r'VERSION\s*=\s*["\']([^"\']+)["\']', bootstrap_text)
if not version_match or not bootstrap_match:
    raise SystemExit("release verification failed: version constants are unreadable")
if version_match.group(1) != bootstrap_match.group(1):
    raise SystemExit("release verification failed: bootstrap/package versions differ")

digest = hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()
expected_digest = CHECKSUM.read_text(encoding="utf-8").split()[0]
if digest != expected_digest:
    raise SystemExit("release verification failed: installer checksum mismatch")

print("release verification PASS: Jervis " + version_match.group(1))
