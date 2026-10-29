"""Private, bounded, structured operational logging for Jervis 8.2.

Only catalogued, fixed messages and typed non-sensitive metrics enter this log.
Transcripts, paths, device IDs, secrets, provider output and stack traces do not.
This journal is separate from legacy conversation and SQLite event history.
"""
from __future__ import annotations

import json
import logging
import os
import re
import stat
import uuid
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Code -> (severity, component, safe display text, recommended action).
CATALOG = {
    "runtime.started": ("INFO", "runtime", "Jervis runtime started", ""),
    "runtime.stopped": ("INFO", "runtime", "Jervis runtime stopped", ""),
    "runtime.crashed": ("ERROR", "runtime", "Jervis runtime terminated unexpectedly",
                        "Run jervis doctor and inspect the crash recovery report."),
    "audio.connected": ("INFO", "audio", "Audio input connected", ""),
    "audio.disconnected": ("WARNING", "audio", "Audio input disconnected",
                           "Check the microphone and audio device selection."),
    "audio.reconnected": ("INFO", "audio", "Audio input reconnected", ""),
    "provider.connected": ("INFO", "provider", "Model provider connected", ""),
    "provider.unavailable": ("WARNING", "provider", "Model provider unavailable",
                             "Check the configured provider and Jervis health."),
    "security.denied": ("WARNING", "security", "An operation was denied by policy",
                        "Review permissions and authenticate before retrying."),
    "mission.started": ("INFO", "mission", "Mission started", ""),
    "mission.completed": ("INFO", "mission", "Mission completed", ""),
    "mission.failed": ("ERROR", "mission", "Mission failed",
                       "Review the mission's permitted steps and retry policy."),
    "backup.failed": ("ERROR", "backup", "Backup operation failed",
                      "Check available space and verify the recovery snapshot."),
    "system.degraded": ("WARNING", "system", "System entered degraded mode",
                        "Inspect Jervis health and resource usage."),
}
_SEVERITY = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40}
_METRIC_FIELDS = frozenset({"duration_ms", "count", "attempt", "retry_after_ms"})
_ID = re.compile(r"[0-9a-fA-F-]{8,64}\Z")


class _PrivateRotatingHandler(RotatingFileHandler):
    """Create current and rotated log files with private mode, never follow symlinks."""

    def _open(self):
        path = Path(self.baseFilename)
        if path.is_symlink():
            raise PermissionError("Refusing a symlinked logging destination")
        flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags, 0o600)
        try:
            if os.name != "nt":
                if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                    raise PermissionError("Logging destination is not a regular file")
                os.fchmod(descriptor, 0o600)
            return os.fdopen(descriptor, "a", encoding="utf-8")
        except BaseException:
            os.close(descriptor)
            raise


class EventJournal:
    """Synchronous, rotating journal; no arbitrary free-form user text accepted."""

    def __init__(self, directory: Path, *, max_bytes: int = 1_048_576,
                 backups: int = 2):
        if not 512 <= max_bytes <= 64 * 1024 * 1024:
            raise ValueError("Invalid journal size")
        if not 1 <= backups <= 5:
            raise ValueError("Invalid journal backup count")
        root = Path(directory)
        if root.is_symlink():
            raise PermissionError("Refusing symlinked log directory")
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if os.name != "nt":
            root.chmod(0o700)
        self._handler = _PrivateRotatingHandler(
            root / "events.jsonl", maxBytes=max_bytes, backupCount=backups,
            encoding="utf-8", delay=False,
        )
        self._handler.setFormatter(logging.Formatter("%(message)s"))

    def emit(self, code: str, *, correlation_id: str | None = None,
             metrics: dict | None = None) -> dict:
        if code not in CATALOG:
            raise ValueError("Unregistered event code")
        if correlation_id is not None and not _ID.fullmatch(correlation_id):
            raise ValueError("Invalid correlation identifier")
        fields = {}
        for key, value in (metrics or {}).items():
            if key not in _METRIC_FIELDS or type(value) not in (int, float):
                raise ValueError("Only approved numeric metrics may be logged")
            if not -1e12 < value < 1e12:
                raise ValueError("Metric outside safe range")
            fields[key] = value
        level, component, message, action = CATALOG[code]
        event = {
            "id": uuid.uuid4().hex,
            "time": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": level,
            "component": component,
            "code": code,
            "message": message,
            "correlation_id": correlation_id or uuid.uuid4().hex,
            "metrics": fields,
        }
        if action:
            event["action"] = action
        record = logging.LogRecord("jervis.events", _SEVERITY[level], "", 0,
                                   json.dumps(event, separators=(",", ":")), (), None)
        self._handler.handle(record)
        return event

    def close(self) -> None:
        self._handler.close()


def read_events(directory: Path, *, level: str | None = None,
                component: str | None = None, limit: int = 100) -> list[dict]:
    """Read oldest-to-newest safely from bounded files; omit malformed records."""
    if not 1 <= limit <= 1000:
        raise ValueError("Limit must be between 1 and 1000")
    if level is not None and level not in _SEVERITY:
        raise ValueError("Unknown log level")
    if component is not None and not re.fullmatch(r"[a-z][a-z0-9_-]{0,47}", component):
        raise ValueError("Invalid component")
    root = Path(directory)
    if root.is_symlink():
        raise PermissionError("Refusing a symlinked log directory")
    rows = []
    for path in (root / "events.jsonl.2", root / "events.jsonl.1",
                 root / "events.jsonl"):
        if not path.is_file() or path.is_symlink():
            continue
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    row = json.loads(line)
                except (ValueError, UnicodeError):
                    continue
                if not isinstance(row, dict) or row.get("code") not in CATALOG:
                    continue
                if level and _SEVERITY[row.get("level", "")] < _SEVERITY[level]:
                    continue
                if component and row.get("component") != component:
                    continue
                # Never print arbitrary on-disk text, even if the file was edited.
                canonical = CATALOG[row["code"]]
                row["level"], row["component"], row["message"] = canonical[:3]
                row["metrics"] = {
                    k: v for k, v in (row.get("metrics") or {}).items()
                    if k in _METRIC_FIELDS and type(v) in (int, float)
                } if isinstance(row.get("metrics"), dict) else {}
                rows.append({k: row.get(k) for k in (
                    "id", "time", "level", "component", "code", "message",
                    "correlation_id", "metrics"
                )})
    return rows[-limit:]


def format_event(event: dict) -> str:
    timestamp = str(event.get("time", ""))[11:23] or "--:--:--"
    level = event.get("level", "?")
    component = event.get("component", "?")
    return f"{timestamp}  {level:<7} {component:<9} {event.get('message', '')}"
