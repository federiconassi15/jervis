from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from .paths import Paths
from .platforms import current_platform
from .snapshots import SnapshotInfo, create_snapshot


def _schedule_binary_delete(binary: Path) -> None:
    if not binary.exists() or not getattr(sys, "frozen", False):
        return
    if platform.system() == "Windows":
        script = (
            "Start-Sleep -Milliseconds 700;"
            "Remove-Item -LiteralPath "
            + repr(str(binary))
            + " -Force -ErrorAction SilentlyContinue"
        )
        subprocess.Popen(
            [
                "powershell",
                "-NoProfile",
                "-WindowStyle",
                "Hidden",
                "-Command",
                script,
            ],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    else:
        subprocess.Popen(
            ["sh", "-c", "sleep 1; rm -f -- " + repr(str(binary))],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def uninstall(
    *,
    purge_data: bool = False,
    remove_binary: bool = False,
    paths: Paths | None = None,
) -> SnapshotInfo:
    resolved = paths or Paths.resolve()
    resolved.ensure()
    snapshot = create_snapshot(
        "pre-uninstall",
        paths=resolved,
        include_binary=remove_binary,
        executable=Path(sys.executable),
    )

    adapter = current_platform()
    try:
        adapter.stop_service()
    except Exception:
        pass
    try:
        adapter.remove_service()
    except Exception:
        pass

    if purge_data:
        # Preserve snapshots so a purge is still reversible.
        for root in (resolved.config, resolved.logs, resolved.cache):
            if root.exists():
                shutil.rmtree(root, ignore_errors=True)
        if resolved.data.exists():
            for item in resolved.data.iterdir():
                if item.name == "snapshots":
                    continue
                if item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)
                else:
                    item.unlink(missing_ok=True)

    if remove_binary:
        _schedule_binary_delete(Path(sys.executable))
    return snapshot
