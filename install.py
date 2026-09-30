#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

REPOSITORY = "federiconassi15/jervis"
RELEASE_LINE = (7, 1)
USER_AGENT = "Jervis-Installer/7.1"


def request_json(url: str):
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/vnd.github+json", "User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def download(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def version_tuple(tag: str):
    value = tag.lstrip("v").split(".")
    if len(value) != 3 or not all(part.isdigit() for part in value):
        return None
    return tuple(int(part) for part in value)


def choose_release():
    releases = request_json(
        "https://api.github.com/repos/" + REPOSITORY + "/releases?per_page=50"
    )
    candidates = []
    for release in releases:
        version = version_tuple(str(release.get("tag_name") or ""))
        if (
            version
            and version[:2] == RELEASE_LINE
            and not release.get("draft")
            and not release.get("prerelease")
        ):
            candidates.append((version, release))
    if not candidates:
        raise RuntimeError("no stable Jervis 7.1.x release is available")
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def asset_url(release, name: str) -> str:
    for asset in release.get("assets", []):
        if asset.get("name") == name:
            return str(asset["browser_download_url"])
    raise RuntimeError("release asset is missing: " + name)


def main() -> None:
    if sys.version_info < (3, 11):
        raise SystemExit("Jervis requires Python 3.11 or newer.")

    release = choose_release()
    installer = download(asset_url(release, "jervis-installer.pyz"))
    checksum_text = download(
        asset_url(release, "jervis-installer.pyz.sha256")
    ).decode("utf-8")
    expected = checksum_text.split()[0].lower()
    actual = hashlib.sha256(installer).hexdigest().lower()
    if actual != expected:
        raise RuntimeError("Jervis installer SHA-256 verification failed")

    with tempfile.TemporaryDirectory(prefix="jervis-download-") as directory:
        path = Path(directory) / "jervis-installer.pyz"
        path.write_bytes(installer)
        subprocess.run([sys.executable, str(path)], check=True)


if __name__ == "__main__":
    main()
