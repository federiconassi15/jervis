from __future__ import annotations

import json
import re
import urllib.request
from dataclasses import dataclass

from .version import VERSION_INFO, __version__


@dataclass(slots=True)
class UpdateInfo:
    available: bool
    current: str
    latest: str | None
    url: str | None
    reason: str


def _version_tuple(value: str):
    match = re.fullmatch(
        r"v?(\d+)\.(\d+)\.(\d+)",
        value.strip(),
    )
    return None if not match else tuple(map(int, match.groups()))


def _select_latest_same_line(releases):
    candidates = []
    for release in releases:
        if release.get("draft") or release.get("prerelease"):
            continue
        version = _version_tuple(str(release.get("tag_name") or ""))
        if version is None or version[:2] != VERSION_INFO[:2]:
            continue
        candidates.append((version, release))

    if not candidates:
        return None, None

    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0]


def check(repo: str = "federiconassi15/jervis") -> UpdateInfo:
    request = urllib.request.Request(
        "https://api.github.com/repos/"
        + repo
        + "/releases?per_page=50",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "Jervis-Updater",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            releases = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        return UpdateInfo(
            False,
            __version__,
            None,
            None,
            "update check failed: " + str(exc),
        )

    version, release = _select_latest_same_line(releases)
    if version is None or release is None:
        return UpdateInfo(
            False,
            __version__,
            None,
            None,
            "no stable release exists on the current Jervis major/minor line",
        )

    latest_text = ".".join(map(str, version))
    if version <= VERSION_INFO:
        return UpdateInfo(
            False,
            __version__,
            latest_text,
            None,
            "already current",
        )

    return UpdateInfo(
        True,
        __version__,
        latest_text,
        str(release.get("html_url") or ""),
        "patch update available",
    )
