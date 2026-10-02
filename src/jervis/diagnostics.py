from __future__ import annotations

import json
import re
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any

from .doctor import run_doctor
from .paths import Paths
from .permissions_audit import audit_permissions
from .status import collect_status
from .version import __version__

_SECRET_KEYS = (
    "key",
    "token",
    "password",
    "passphrase",
    "secret",
    "credential",
    "auth",
    "serial",
)
_SECRET_RE = re.compile(
    r"(?i)(api[_ -]?key|token|password|passphrase|secret|bearer)\s*[:=]\s*\S+"
)
_PRIVATE_IPV4_RE = re.compile(
    r"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
    r"192\.168\.\d{1,3}\.\d{1,3}|"
    r"172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b"
)


def _redact(value: Any, key: str = "") -> Any:
    lowered = key.lower()
    if any(part in lowered for part in _SECRET_KEYS):
        return "<redacted>"
    if isinstance(value, dict):
        return {str(k): _redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, str):
        cleaned = _SECRET_RE.sub(r"\1=<redacted>", value)
        cleaned = _PRIVATE_IPV4_RE.sub("<private-ip>", cleaned)
        home = str(Path.home())
        if home and home != "/":
            cleaned = cleaned.replace(home, "~")
        return cleaned
    return value


def create_diagnostics_bundle(
    destination: Path | None = None,
    *,
    paths: Paths | None = None,
) -> Path:
    resolved = paths or Paths.resolve()
    resolved.ensure()
    if destination is None:
        destination = (
            resolved.root
            / ("jervis-diagnostics-" + time.strftime("%Y%m%d-%H%M%S") + ".zip")
        )
    destination = destination.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)

    report = {
        "jervis_version": __version__,
        "status": _redact(collect_status(resolved)),
        "doctor": [
            {"ok": item.ok, "component": item.component, "detail": _redact(item.detail)}
            for item in run_doctor().checks
        ],
        "permissions": _redact(audit_permissions(resolved)),
    }

    config_path = resolved.config / "config.json"
    if config_path.exists():
        try:
            report["config_shape"] = _redact(
                json.loads(config_path.read_text(encoding="utf-8"))
            )
        except Exception as exc:
            report["config_error"] = str(exc)

    with tempfile.TemporaryDirectory(prefix="jervis-diag-", dir=resolved.cache) as tmp:
        root = Path(tmp)
        (root / "diagnostics.json").write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        (root / "recent-logs.txt").write_text(
            "Raw logs are omitted by default to avoid leaking transcripts, "
            "device identifiers, private paths, or provider data.\n",
            encoding="utf-8",
        )

        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(root / "diagnostics.json", "diagnostics.json")
            archive.write(root / "recent-logs.txt", "recent-logs.txt")
    return destination
