#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

REPOSITORY = "federiconassi15/jervis"
RELEASE_LINE = (7, 1)
USER_AGENT = "Jervis-Installer/7.1"
BLUE = "\033[38;5;45m"
GREEN = "\033[38;5;82m"
RED = "\033[38;5;203m"
RESET = "\033[0m"


def paint(text: str, color: str) -> str:
    return color + text + RESET if sys.stdout.isatty() else text


class Spinner:
    frames = ["◐", "◓", "◑", "◒"]

    def __init__(self, label: str) -> None:
        self.label = label
        self.running = False
        self.thread: threading.Thread | None = None

    def __enter__(self):
        self.running = True
        if sys.stdout.isatty():
            self.thread = threading.Thread(target=self._loop, daemon=True)
            self.thread.start()
        else:
            print(self.label)
        return self

    def _loop(self) -> None:
        index = 0
        while self.running:
            print(
                "\r" + paint("  " + self.frames[index % 4] + "  " + self.label, BLUE),
                end="",
                flush=True,
            )
            index += 1
            time.sleep(0.12)

    def __exit__(self, exc_type, exc, tb):
        self.running = False
        if self.thread:
            self.thread.join(timeout=0.5)
        if sys.stdout.isatty():
            print("\r" + " " * (len(self.label) + 12) + "\r", end="", flush=True)
        if exc_type is None:
            print(paint("  ✓  " + self.label, GREEN))
        return False


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
        raise RuntimeError("No stable Jervis 7.1.x release is available yet.")
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def asset_url(release, name: str) -> str:
    for asset in release.get("assets", []):
        if asset.get("name") == name:
            return str(asset["browser_download_url"])
    raise RuntimeError("The release is missing " + name + ".")


def main() -> None:
    if sys.version_info < (3, 11):
        raise SystemExit("Jervis requires Python 3.11 or newer.")

    try:
        print()
        print(paint("  J E R V I S", BLUE))
        print()
        with Spinner("Finding the latest Jervis 7.1 release"):
            release = choose_release()
        with Spinner("Downloading the verified installer"):
            installer = download(asset_url(release, "jervis-installer.pyz"))
            checksum_text = download(
                asset_url(release, "jervis-installer.pyz.sha256")
            ).decode("utf-8")
            expected = checksum_text.split()[0].lower()
            actual = hashlib.sha256(installer).hexdigest().lower()
            if actual != expected:
                raise RuntimeError("Installer checksum verification failed.")

        with tempfile.TemporaryDirectory(prefix="jervis-download-") as directory:
            path = Path(directory) / "jervis-installer.pyz"
            path.write_bytes(installer)
            subprocess.run([sys.executable, str(path)], check=True)

    except KeyboardInterrupt:
        print()
        print("Jervis setup cancelled.")
    except Exception as exc:
        print()
        print(paint("  ✕  Jervis could not start", RED))
        print("  " + str(exc))


if __name__ == "__main__":
    main()
