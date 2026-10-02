from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .config import load
from .doctor import run_doctor
from .fast import NATIVE_AVAILABLE
from .openclaw_setup import doctor as openclaw_doctor
from .openclaw_setup import find_openclaw
from .paths import Paths
from .platforms import current_platform


@dataclass(slots=True)
class AcceptanceCheck:
    name: str
    ok: bool
    detail: str


def run_acceptance(paths: Paths | None = None) -> list[AcceptanceCheck]:
    resolved = paths or Paths.resolve()
    resolved.ensure()
    checks: list[AcceptanceCheck] = []

    try:
        load(resolved.config / "config.json")
        checks.append(AcceptanceCheck("config", True, "configuration loads"))
    except Exception as exc:
        checks.append(AcceptanceCheck("config", False, str(exc)))

    database = resolved.data / "jervis.sqlite3"
    try:
        if not database.exists():
            raise FileNotFoundError("Jervis database is missing")
        uri = "file:" + database.resolve().as_posix() + "?mode=ro"
        db = sqlite3.connect(uri, uri=True)
        result = db.execute("PRAGMA quick_check").fetchone()
        db.close()
        detail = str(result[0] if result else "no result")
        checks.append(AcceptanceCheck("database", detail == "ok", detail))
    except Exception as exc:
        checks.append(AcceptanceCheck("database", False, str(exc)))

    adapter = current_platform()
    try:
        health = adapter.service_health()
        checks.append(AcceptanceCheck("startup", health.ok, health.detail))
    except Exception as exc:
        checks.append(AcceptanceCheck("startup", False, str(exc)))

    cli = find_openclaw()
    if cli:
        ok, detail = openclaw_doctor(cli)
        checks.append(AcceptanceCheck("openclaw", ok, detail or "doctor completed"))
    else:
        checks.append(AcceptanceCheck("openclaw", False, "OpenClaw missing"))

    checks.append(
        AcceptanceCheck(
            "native_acceleration",
            NATIVE_AVAILABLE,
            "Rust acceleration active" if NATIVE_AVAILABLE else "NumPy fallback active",
        )
    )

    report = run_doctor()
    checks.append(
        AcceptanceCheck(
            "doctor",
            report.ok,
            "all doctor checks passed" if report.ok else "one or more doctor checks failed",
        )
    )
    return checks
