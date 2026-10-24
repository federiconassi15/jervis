"""Jervis 8.1 local core: deterministic offline intents, health and plugin discovery.

No network calls or subprocess execution occur in this module.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from .paths import Paths
from .recovery_verify import verify_snapshot_archive


@dataclass(frozen=True)
class OfflineIntent:
    name: str
    response: str
    requires_confirmation: bool = False


def resolve_offline(text: str) -> OfflineIntent | None:
    """Recognize enumerated, safe offline intents; never guess an action."""
    command = " ".join(text.casefold().strip().split()).rstrip("?.!")
    if len(command) > 128:
        return None
    intent_names = {
        "help": "help", "what can you do": "help", "commands": "help",
        "hello": "greeting", "hi": "greeting", "hey": "greeting",
        "hello jervis": "greeting", "good morning": "greeting",
        "good evening": "greeting",
        "status": "status", "system status": "status",
        "diagnostics": "diagnostics", "run diagnostics": "diagnostics",
        "time": "time", "what time is it": "time", "current time": "time",
        "what's the time": "time",
    }
    canonical = {
        "help": "Try status, help, time, or diagnostics.",
        "greeting": "Hello. Jervis is ready.",
        "status": "Run jervis status for detailed system health.",
        "diagnostics": "Run jervis doctor for diagnostics.",
        "time": "Use the local clock for the current time.",
    }
    name = intent_names.get(command)
    return OfflineIntent(name, canonical[name]) if name is not None else None

@dataclass(frozen=True)
class PluginManifest:
    identifier: str
    version: str
    description: str
    permissions: tuple[str, ...]


_ALLOWED_PERMISSIONS = frozenset({"status.read", "audio.read", "notifications.send"})


def discover_plugins(directory: Path) -> list[PluginManifest]:
    """Read manifests only. Plugins are NEVER executed or imported."""
    if not directory.exists():
        return []
    plugins = []
    for path in sorted(directory.glob("*/plugin.json")):
        if path.is_symlink() or path.parent.is_symlink():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            identifier = data["id"]
            version = data["version"]
            permissions = data.get("permissions", [])
            if not isinstance(identifier, str) or not re.fullmatch(r"[a-z0-9][a-z0-9.-]{0,63}", identifier):
                continue
            if not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+", version):
                continue
            if not isinstance(permissions, list) or any(p not in _ALLOWED_PERMISSIONS for p in permissions):
                continue
            description = data.get("description", "")
            if not isinstance(description, str):
                continue
            plugins.append(PluginManifest(identifier, version, description[:240], tuple(permissions)))
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return plugins


def health_summary(paths: Paths | None = None) -> dict:
    paths = paths or Paths.resolve()
    config = paths.config / "config.json"
    db = paths.data / "jervis.sqlite3"
    archives = sorted((paths.data / "snapshots").glob("*.tar.gz"))
    verified = sum(verify_snapshot_archive(path) for path in archives)
    return {
        "config_present": config.is_file(),
        "database_present": db.is_file(),
        "plugins_discovered": len(discover_plugins(paths.data / "plugins")),
        "recovery_snapshots": verified,
        "invalid_snapshots": len(archives) - verified,
    }


def render_plugins(paths: Paths | None = None) -> list[dict]:
    paths = paths or Paths.resolve()
    return [asdict(p) for p in discover_plugins(paths.data / "plugins")]
