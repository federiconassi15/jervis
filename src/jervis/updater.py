from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .paths import Paths
from .snapshots import SnapshotInfo, create_snapshot, list_snapshots, restore_snapshot
from .version import VERSION_INFO, __version__


@dataclass(slots=True)
class UpdateInfo:
    available: bool
    current: str
    latest: str | None
    url: str | None
    reason: str


@dataclass(slots=True)
class UpdateResult:
    ok: bool
    current: str
    target: str | None
    detail: str
    snapshot_id: str | None = None
    restart_required: bool = False


def _version_tuple(value: str):
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", value.strip())
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


def _releases(repo: str) -> list[dict[str, Any]]:
    request = urllib.request.Request(
        "https://api.github.com/repos/" + repo + "/releases?per_page=50",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "Jervis-Updater"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        data = json.loads(response.read().decode("utf-8"))
    return data if isinstance(data, list) else []


def check(repo: str = "federiconassi15/jervis") -> UpdateInfo:
    try:
        releases = _releases(repo)
    except Exception as exc:
        return UpdateInfo(False, __version__, None, None, "update check failed: " + str(exc))

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
        return UpdateInfo(False, __version__, latest_text, None, "already current")

    return UpdateInfo(
        True,
        __version__,
        latest_text,
        str(release.get("html_url") or ""),
        "patch update available",
    )


def _asset_name() -> str:
    system = platform.system()
    machine = platform.machine().lower()
    arm64 = machine in {"arm64", "aarch64"}
    if system == "Linux":
        return "jervis-linux-arm64" if arm64 else "jervis-linux-x64"
    if system == "Darwin":
        return "jervis-macos-arm64" if arm64 else "jervis-macos-x64"
    if system == "Windows":
        if arm64:
            raise RuntimeError("official Windows ARM64 native builds are not published yet")
        return "jervis-windows-x64.exe"
    raise RuntimeError("unsupported update platform: " + system)


def _asset(release: dict[str, Any], name: str) -> dict[str, Any]:
    for asset in release.get("assets") or []:
        if str(asset.get("name") or "") == name:
            return asset
    raise RuntimeError("release is missing required asset: " + name)


def _download(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "Jervis-Updater"})
    with urllib.request.urlopen(request, timeout=120) as response:
        destination.write_bytes(response.read())


def _checksums(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        parts = line.strip().split()
        if len(parts) >= 2 and re.fullmatch(r"[0-9a-fA-F]{64}", parts[0]):
            out[parts[-1].lstrip("*")] = parts[0].lower()
    return out


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _smoke_binary(binary: Path) -> tuple[bool, str]:
    try:
        mode = binary.stat().st_mode
        if platform.system() != "Windows":
            binary.chmod(mode | stat.S_IXUSR)
        version = subprocess.run(
            [str(binary), "--version"],
            text=True,
            capture_output=True,
            timeout=20,
            check=False,
        )
        runtime = subprocess.run(
            [str(binary), "runtime-info"],
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
        ok = version.returncode == 0 and runtime.returncode == 0
        detail = (
            (version.stdout or version.stderr or "").strip()
            + " | "
            + (runtime.stdout or runtime.stderr or "").strip()
        )
        return ok, detail[-2000:]
    except Exception as exc:
        return False, str(exc)


def _replace_native(binary: Path, staged: Path, paths: Paths) -> bool:
    if platform.system() == "Windows":
        script = paths.cache / "finish-update.ps1"
        pending = paths.cache / "pending-update.json"
        pending.write_text(
            json.dumps(
                {
                    "current": str(binary),
                    "staged": str(staged),
                    "target_version": staged.parent.name,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        previous = paths.cache / "previous-jervis.exe"
        script.write_text(
            "$ErrorActionPreference='Stop'\n"
            "Start-Sleep -Milliseconds 900\n"
            "$src=" + repr(str(staged)) + "\n"
            "$dst=" + repr(str(binary)) + "\n"
            "$old=" + repr(str(previous)) + "\n"
            "Copy-Item -LiteralPath $dst -Destination $old -Force\n"
            "Copy-Item -LiteralPath $src -Destination $dst -Force\n"
            "& $dst --version | Out-Null\n"
            "if($LASTEXITCODE -ne 0){Copy-Item -LiteralPath $old -Destination $dst -Force}\n"
            "Remove-Item -LiteralPath " + repr(str(pending)) + " -Force -ErrorAction SilentlyContinue\n",
            encoding="utf-8",
        )
        subprocess.Popen(
            [
                "powershell",
                "-NoProfile",
                "-WindowStyle",
                "Hidden",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script),
            ],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return True

    mode = binary.stat().st_mode if binary.exists() else (stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    staged.chmod(mode | stat.S_IXUSR)
    previous = paths.cache / ("previous-" + binary.name)
    if binary.exists():
        shutil.copy2(binary, previous)
    temp = binary.with_name(binary.name + ".new")
    shutil.copy2(staged, temp)
    temp.chmod(mode | stat.S_IXUSR)
    os.replace(temp, binary)
    ok, _detail = _smoke_binary(binary)
    if not ok and previous.exists():
        rollback = binary.with_name(binary.name + ".rollback")
        shutil.copy2(previous, rollback)
        rollback.chmod(mode | stat.S_IXUSR)
        os.replace(rollback, binary)
        raise RuntimeError("new Jervis binary failed startup smoke test; previous binary restored")
    return True


def apply_update(
    repo: str = "federiconassi15/jervis",
    *,
    paths: Paths | None = None,
) -> UpdateResult:
    resolved = paths or Paths.resolve()
    resolved.ensure()

    try:
        releases = _releases(repo)
        version, release = _select_latest_same_line(releases)
    except Exception as exc:
        return UpdateResult(False, __version__, None, "update lookup failed: " + str(exc))

    if version is None or release is None or version <= VERSION_INFO:
        latest = None if version is None else ".".join(map(str, version))
        return UpdateResult(True, __version__, latest, "already current")

    target = ".".join(map(str, version))
    if not getattr(sys, "frozen", False):
        return UpdateResult(
            False,
            __version__,
            target,
            "self-update is supported for official native builds; source installs should reinstall from the release wheel/source archive",
        )

    binary = Path(sys.executable).resolve()
    snapshot = create_snapshot(
        "pre-update-" + target,
        paths=resolved,
        include_binary=True,
        executable=binary,
    )

    try:
        asset_name = _asset_name()
        binary_asset = _asset(release, asset_name)
        sums_asset = _asset(release, "SHA256SUMS")
        stage_dir = resolved.cache / "updates" / target
        stage_dir.mkdir(parents=True, exist_ok=True)
        staged = stage_dir / asset_name
        sums = stage_dir / "SHA256SUMS"
        _download(str(binary_asset["browser_download_url"]), staged)
        _download(str(sums_asset["browser_download_url"]), sums)
        expected = _checksums(sums.read_text(encoding="utf-8")).get(asset_name)
        if not expected:
            raise RuntimeError("SHA256SUMS does not contain " + asset_name)
        actual = _sha256(staged)
        if actual != expected:
            raise RuntimeError("checksum mismatch for " + asset_name)
        smoke_ok, smoke_detail = _smoke_binary(staged)
        if not smoke_ok:
            raise RuntimeError("downloaded binary failed startup smoke test: " + smoke_detail)
        _replace_native(binary, staged, resolved)
    except Exception as exc:
        try:
            restore_snapshot(snapshot.id, paths=resolved, make_guard=False)
        except Exception:
            pass
        return UpdateResult(
            False,
            __version__,
            target,
            "update failed and rollback was attempted: " + str(exc),
            snapshot.id,
        )

    return UpdateResult(
        True,
        __version__,
        target,
        "verified update installed" if platform.system() != "Windows" else "verified update staged; replacement will finish after this process exits",
        snapshot.id,
        restart_required=True,
    )


def rollback_update(
    snapshot_id: str | None = None,
    *,
    paths: Paths | None = None,
) -> UpdateResult:
    resolved = paths or Paths.resolve()
    if snapshot_id is None:
        candidates = [item for item in list_snapshots(paths=resolved) if item.reason.startswith("pre-update-")]
        if not candidates:
            return UpdateResult(False, __version__, None, "no pre-update snapshot exists")
        snapshot_id = candidates[0].id
    try:
        info = restore_snapshot(snapshot_id, paths=resolved, restore_binary=True)
    except Exception as exc:
        return UpdateResult(False, __version__, None, "rollback failed: " + str(exc), snapshot_id)
    return UpdateResult(
        True,
        __version__,
        info.version,
        "snapshot restored; restart Jervis to finish rollback",
        snapshot_id,
        restart_required=True,
    )
