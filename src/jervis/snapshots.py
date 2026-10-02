from __future__ import annotations

import json
import os
import platform
import subprocess
import shutil
import sqlite3
import sys
import tarfile
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from .paths import Paths
from .platforms import current_platform
from .version import __version__


@dataclass(slots=True)
class SnapshotInfo:
    id: str
    created_at: float
    reason: str
    version: str
    archive: str
    includes_binary: bool


def _root(paths: Paths) -> Path:
    root = paths.data / "snapshots"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_reason(value: str) -> str:
    cleaned = "".join(c if c.isalnum() or c in "-_" else "-" for c in value.lower())
    return cleaned.strip("-")[:48] or "manual"


def create_snapshot(
    reason: str,
    *,
    paths: Paths | None = None,
    include_binary: bool = False,
    executable: Path | None = None,
) -> SnapshotInfo:
    resolved = paths or Paths.resolve()
    resolved.ensure()
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
    snapshot_id = stamp + "-" + _safe_reason(reason)
    archive = _root(resolved) / (snapshot_id + ".tar.gz")
    metadata = SnapshotInfo(
        id=snapshot_id,
        created_at=time.time(),
        reason=reason,
        version=__version__,
        archive=str(archive),
        includes_binary=bool(include_binary),
    )

    with tempfile.TemporaryDirectory(prefix="jervis-snapshot-", dir=resolved.cache) as tmp:
        staging = Path(tmp)
        meta = staging / "snapshot.json"
        meta.write_text(json.dumps(asdict(metadata), indent=2) + "\n", encoding="utf-8")

        if resolved.config.exists():
            shutil.copytree(resolved.config, staging / "config", dirs_exist_ok=True)

        data_target = staging / "data"
        data_target.mkdir(parents=True, exist_ok=True)
        if resolved.data.exists():
            for item in resolved.data.iterdir():
                if item.name in {"snapshots", "models", "tools"}:
                    continue
                if item.name in {"jervis.sqlite3-wal", "jervis.sqlite3-shm"}:
                    continue
                target = data_target / item.name
                if item.name == "jervis.sqlite3" and item.is_file():
                    source_db = sqlite3.connect(
                        "file:" + item.resolve().as_posix() + "?mode=ro",
                        uri=True,
                        timeout=5.0,
                    )
                    target_db = sqlite3.connect(target)
                    try:
                        source_db.backup(target_db)
                    finally:
                        target_db.close()
                        source_db.close()
                elif item.is_dir():
                    shutil.copytree(item, target, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, target)

        if include_binary:
            binary = executable or Path(sys.executable)
            if binary.exists() and binary.is_file():
                target = staging / "binary"
                target.mkdir(parents=True, exist_ok=True)
                shutil.copy2(binary, target / binary.name)

        with tarfile.open(archive, "w:gz") as bundle:
            for item in staging.iterdir():
                bundle.add(item, arcname=item.name)

    prune_snapshots(paths=resolved)
    return metadata


def list_snapshots(*, paths: Paths | None = None) -> list[SnapshotInfo]:
    resolved = paths or Paths.resolve()
    found: list[SnapshotInfo] = []
    for archive in sorted(_root(resolved).glob("*.tar.gz"), reverse=True):
        try:
            with tarfile.open(archive, "r:gz") as bundle:
                member = bundle.getmember("snapshot.json")
                raw = bundle.extractfile(member)
                if raw is None:
                    continue
                data = json.loads(raw.read().decode("utf-8"))
            info = SnapshotInfo(**data)
            info.archive = str(archive)
            found.append(info)
        except Exception:
            continue
    return found


def prune_snapshots(*, paths: Paths | None = None, keep: int = 12) -> None:
    resolved = paths or Paths.resolve()
    archives = sorted(_root(resolved).glob("*.tar.gz"), key=lambda p: p.stat().st_mtime, reverse=True)
    for archive in archives[max(1, int(keep)):]:
        archive.unlink(missing_ok=True)


def _find_snapshot(snapshot_id: str, paths: Paths) -> Path:
    direct = _root(paths) / (snapshot_id + ".tar.gz")
    if direct.exists():
        return direct
    matches = [p for p in _root(paths).glob("*.tar.gz") if p.name.startswith(snapshot_id)]
    if len(matches) == 1:
        return matches[0]
    raise FileNotFoundError("snapshot not found: " + snapshot_id)


def restore_snapshot(
    snapshot_id: str,
    *,
    paths: Paths | None = None,
    make_guard: bool = True,
    restore_binary: bool = True,
) -> SnapshotInfo:
    resolved = paths or Paths.resolve()
    archive = _find_snapshot(snapshot_id, resolved)

    if make_guard:
        create_snapshot("pre-rollback-guard", paths=resolved, include_binary=False)

    adapter = current_platform()
    was_installed = adapter.service_installed()
    try:
        if was_installed:
            adapter.stop_service()
    except Exception:
        pass

    with tempfile.TemporaryDirectory(prefix="jervis-restore-", dir=resolved.cache) as tmp:
        staging = Path(tmp)
        with tarfile.open(archive, "r:gz") as bundle:
            for member in bundle.getmembers():
                target = (staging / member.name).resolve()
                if staging.resolve() not in target.parents and target != staging.resolve():
                    raise RuntimeError("unsafe path in snapshot")
                if member.issym() or member.islnk():
                    raise RuntimeError("snapshot contains unsupported link entry")
            bundle.extractall(staging)

        data = json.loads((staging / "snapshot.json").read_text(encoding="utf-8"))
        info = SnapshotInfo(**data)

        config_src = staging / "config"
        if config_src.exists():
            if resolved.config.exists():
                shutil.rmtree(resolved.config)
            shutil.copytree(config_src, resolved.config)

        data_src = staging / "data"
        if data_src.exists():
            resolved.data.mkdir(parents=True, exist_ok=True)
            for item in list(resolved.data.iterdir()):
                if item.name in {"snapshots", "models", "tools"}:
                    continue
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink(missing_ok=True)
            for item in data_src.iterdir():
                target = resolved.data / item.name
                if item.is_dir():
                    shutil.copytree(item, target)
                else:
                    shutil.copy2(item, target)

        if restore_binary:
            binary_dir = staging / "binary"
            binaries = list(binary_dir.iterdir()) if binary_dir.exists() else []
            current = Path(sys.executable)
            if binaries and current.exists() and os.access(current.parent, os.W_OK):
                if platform.system() == "Windows" and getattr(sys, "frozen", False):
                    staged_binary = resolved.cache / "rollback-binary.exe"
                    shutil.copy2(binaries[0], staged_binary)
                    script = resolved.cache / "finish-rollback.ps1"
                    script.write_text(
                        "Start-Sleep -Milliseconds 900\n"
                        "$src=" + repr(str(staged_binary)) + "\n"
                        "$dst=" + repr(str(current)) + "\n"
                        "Copy-Item -LiteralPath $src -Destination $dst -Force\n",
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
                else:
                    temp = current.with_name(current.name + ".rollback")
                    shutil.copy2(binaries[0], temp)
                    os.replace(temp, current)

    try:
        if was_installed:
            adapter.start_service()
    except Exception:
        pass
    return info
