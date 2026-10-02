from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .fast import NATIVE_AVAILABLE, backend_name
from .lifecycle import marker_path
from .openclaw_setup import doctor as openclaw_doctor
from .openclaw_setup import find_openclaw
from .paths import Paths
from .platforms import current_platform
from .snapshots import list_snapshots
from .version import __version__


def _crash_state(paths: Paths) -> dict[str, Any]:
    marker = marker_path(paths)
    if not marker.exists():
        return {"previous_unclean": False, "consecutive_crashes": 0}
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
    except Exception:
        return {"previous_unclean": True, "consecutive_crashes": 1}
    return {
        "previous_unclean": not bool(data.get("clean", False)),
        "consecutive_crashes": int(data.get("consecutive_crashes", 0)),
        "started_at": data.get("started_at"),
    }


def _latest_benchmark(paths: Paths) -> dict[str, Any] | None:
    history = paths.data / "benchmark-history.jsonl"
    if not history.exists():
        return None
    try:
        lines = [line for line in history.read_text(encoding="utf-8").splitlines() if line.strip()]
        if not lines:
            return None
        return json.loads(lines[-1])
    except Exception:
        return None


def collect_status(paths: Paths | None = None) -> dict[str, Any]:
    resolved = paths or Paths.resolve()
    resolved.ensure()
    adapter = current_platform()
    try:
        service = adapter.service_health()
        service_ok = service.ok
        service_detail = service.detail
    except Exception as exc:
        service_ok = False
        service_detail = str(exc)

    openclaw = find_openclaw()
    openclaw_ok = False
    openclaw_detail = "missing"
    if openclaw:
        try:
            openclaw_ok, openclaw_detail = openclaw_doctor(openclaw)
        except Exception as exc:
            openclaw_detail = str(exc)

    benchmark = _latest_benchmark(resolved)
    latency = None
    if benchmark:
        live = benchmark.get("live", {})
        stats = live.get("command_to_reply_ms") if isinstance(live, dict) else None
        if isinstance(stats, dict):
            latency = stats.get("median")

    snapshots = list_snapshots(paths=resolved)
    return {
        "version": __version__,
        "platform": adapter.capabilities().name,
        "service": {"ok": service_ok, "detail": service_detail},
        "openclaw": {
            "installed": bool(openclaw),
            "ok": openclaw_ok,
            "detail": openclaw_detail,
        },
        "acceleration": {
            "backend": backend_name(),
            "native": NATIVE_AVAILABLE,
        },
        "latency_ms": latency,
        "snapshots": len(snapshots),
        "last_snapshot": snapshots[0].id if snapshots else None,
        "crash": _crash_state(resolved),
        "time": time.time(),
    }


def render_status(status: dict[str, Any]) -> str:
    service = status["service"]
    openclaw = status["openclaw"]
    crash = status["crash"]
    latency = status.get("latency_ms")
    rows = [
        ("CORE", "● ONLINE"),
        ("SERVICE", ("● " if service["ok"] else "! ") + str(service["detail"]).upper()),
        ("OPENCLAW", ("● ONLINE" if openclaw["ok"] else "! " + str(openclaw["detail"]))),
        (
            "ACCEL",
            ("● " if status["acceleration"]["native"] else "○ ")
            + str(status["acceleration"]["backend"]).upper(),
        ),
        ("LATENCY", "—" if latency is None else format(float(latency), ".0f") + " ms median"),
        ("SNAPSHOTS", str(status["snapshots"])),
        (
            "RECOVERY",
            (
                "! previous run unclean · crashes=" + str(crash["consecutive_crashes"])
                if crash["previous_unclean"]
                else "● clean"
            ),
        ),
    ]
    width = 58
    lines = ["┌─ JERVIS " + str(status["version"]) + " // SYSTEM STATUS " + "─" * 18 + "┐"]
    for key, value in rows:
        body = "│ " + key.ljust(11) + str(value)
        lines.append(body[:width].ljust(width) + "│")
    lines.append("└" + "─" * width + "┘")
    return "\n".join(lines)
