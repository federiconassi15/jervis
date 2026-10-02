from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Any

from .openclaw_setup import find_openclaw
from .paths import Paths
from .platforms import current_platform


def _mode(path: Path) -> str:
    try:
        return oct(stat.S_IMODE(path.stat().st_mode))
    except OSError:
        return "unavailable"


def audit_permissions(paths: Paths | None = None) -> dict[str, Any]:
    resolved = paths or Paths.resolve()
    adapter = current_platform()
    openclaw = find_openclaw()
    config = resolved.config / "config.json"
    database = resolved.data / "jervis.sqlite3"
    return {
        "platform": adapter.capabilities().name,
        "startup_installed": adapter.service_installed(),
        "paths": {
            "config": {"path": str(config), "exists": config.exists(), "mode": _mode(config)},
            "database": {"path": str(database), "exists": database.exists(), "mode": _mode(database)},
            "data_root": {"path": str(resolved.data), "exists": resolved.data.exists(), "mode": _mode(resolved.data)},
        },
        "openclaw": {
            "path": str(openclaw) if openclaw else None,
            "exists": bool(openclaw),
            "capability_boundary": (
                "external agent runtime; tool/shell/filesystem/network permissions are "
                "defined by OpenClaw configuration and installed plugins"
            ),
        },
        "jervis_capabilities": {
            "microphone": True,
            "audio_output": True,
            "network": True,
            "shell": False,
            "managed_filesystem_roots": [
                str(resolved.config),
                str(resolved.data),
                str(resolved.logs),
                str(resolved.cache),
            ],
            "skills_directory": str(resolved.data / "skills"),
            "mcp": "delegated to OpenClaw; inspect OpenClaw configuration for active servers/tools",
        },
        "effective_user": (
            str(os.geteuid()) if hasattr(os, "geteuid") else os.environ.get("USERNAME", "unknown")
        ),
    }
