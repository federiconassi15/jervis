from __future__ import annotations

import os
import shutil
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

from .audio.devices import list_devices
from .config import load
from .openclaw_setup import doctor as openclaw_doctor
from .openclaw_setup import find_openclaw, install_official
from .paths import Paths
from .permissions_audit import audit_permissions
from .platforms import current_platform
from .prereqs import ensure_linux_audio, ensure_linux_openclaw_tools
from .snapshots import create_snapshot
from .speaker_model import ensure_speaker_model


@dataclass(slots=True)
class RepairResult:
    component: str
    ok: bool
    detail: str
    snapshot_id: str | None = None


def _snapshot(component: str, paths: Paths) -> str:
    return create_snapshot("pre-repair-" + component, paths=paths).id


def repair_audio(paths: Paths) -> RepairResult:
    snap = _snapshot("audio", paths)
    try:
        ensure_linux_audio(lambda _message: True)
        devices = list_devices()
        inputs = sum(1 for device in devices if device.inputs > 0)
        outputs = sum(1 for device in devices if device.outputs > 0)
        if not devices:
            return RepairResult("audio", False, "no audio devices are visible", snap)
        return RepairResult("audio", True, f"{inputs} inputs / {outputs} outputs visible", snap)
    except Exception as exc:
        return RepairResult("audio", False, str(exc), snap)


def repair_openclaw(paths: Paths) -> RepairResult:
    snap = _snapshot("openclaw", paths)
    try:
        cli = find_openclaw()
        if cli is None:
            ensure_linux_openclaw_tools()
            cli = install_official(lambda _message: None)
        healthy, detail = openclaw_doctor(cli)
        return RepairResult(
            "openclaw",
            healthy,
            "doctor passed" if healthy else (detail or "doctor reported a problem"),
            snap,
        )
    except Exception as exc:
        return RepairResult("openclaw", False, str(exc), snap)


def repair_database(paths: Paths) -> RepairResult:
    snap = _snapshot("database", paths)
    database = paths.data / "jervis.sqlite3"
    try:
        if not database.exists():
            return RepairResult("database", True, "database does not exist yet", snap)
        db = sqlite3.connect(database)
        check = db.execute("PRAGMA integrity_check").fetchone()
        if not check or str(check[0]) != "ok":
            detail = str(check[0] if check else "integrity check failed")
            db.close()
            return RepairResult("database", False, detail, snap)
        db.execute("PRAGMA optimize")
        db.commit()
        db.close()
        return RepairResult("database", True, "integrity check passed; optimized", snap)
    except Exception as exc:
        return RepairResult("database", False, str(exc), snap)


def _launcher() -> Path:
    found = shutil.which("jervis")
    if found:
        return Path(found)
    return Path(sys.executable)


def repair_startup(paths: Paths) -> RepairResult:
    snap = _snapshot("startup", paths)
    try:
        config = load(paths.config / "config.json")
        adapter = current_platform()
        try:
            adapter.stop_service()
        except Exception:
            pass
        try:
            adapter.remove_service()
        except Exception:
            pass
        if config["install"].get("start_at_boot", True):
            adapter.install_service(
                _launcher(),
                paths.service_environment(),
                mode=str(config["install"]["mode"]),
            )
            health = adapter.service_health()
            return RepairResult("startup", health.ok, health.detail, snap)
        return RepairResult("startup", True, "startup intentionally disabled", snap)
    except Exception as exc:
        return RepairResult("startup", False, str(exc), snap)


def repair_models(paths: Paths) -> RepairResult:
    snap = _snapshot("models", paths)
    try:
        model = paths.data / "models" / "speaker.onnx"
        ok = ensure_speaker_model(model, lambda _message: None)
        return RepairResult(
            "models",
            bool(ok),
            "speaker model available" if ok else "speaker model could not be repaired",
            snap,
        )
    except Exception as exc:
        return RepairResult("models", False, str(exc), snap)


def repair_permissions(paths: Paths) -> RepairResult:
    snap = _snapshot("permissions", paths)
    try:
        if os.name != "nt":
            for target in (paths.config / "config.json", paths.data / "jervis.sqlite3"):
                if target.exists():
                    target.chmod(0o600)
            for target in (paths.config, paths.data):
                if target.exists():
                    target.chmod(0o700)
        audit = audit_permissions(paths)
        return RepairResult("permissions", True, "local Jervis file permissions normalized", snap)
    except Exception as exc:
        return RepairResult("permissions", False, str(exc), snap)


def repair(component: str, *, paths: Paths | None = None) -> RepairResult | list[RepairResult]:
    resolved = paths or Paths.resolve()
    resolved.ensure()
    mapping = {
        "audio": repair_audio,
        "openclaw": repair_openclaw,
        "database": repair_database,
        "startup": repair_startup,
        "models": repair_models,
        "permissions": repair_permissions,
    }
    if component == "all":
        return [mapping[name](resolved) for name in mapping]
    if component not in mapping:
        raise ValueError("unknown repair component: " + component)
    return mapping[component](resolved)


def render_repair_center(*, paths: Paths | None = None) -> str:
    resolved = paths or Paths.resolve()
    adapter = current_platform()
    try:
        audio_detail = "ready" if list_devices() else "attention"
    except Exception as exc:
        audio_detail = "attention · " + str(exc)
    checks = {
        "AUDIO": audio_detail,
        "OPENCLAW": "installed" if find_openclaw() else "missing",
        "STARTUP": adapter.service_health().detail,
        "DATABASE": "present" if (resolved.data / "jervis.sqlite3").exists() else "new",
        "MODELS": "present" if (resolved.data / "models" / "speaker.onnx").exists() else "missing",
        "PERMISSIONS": "auditable",
    }
    width = 58
    lines = ["┌─ JERVIS // REPAIR CENTER " + "─" * 32 + "┐"]
    for name, detail in checks.items():
        row = "│ " + name.ljust(14) + str(detail)
        lines.append(row[:width].ljust(width) + "│")
    lines.append("├─ run: jervis repair <component|all> " + "─" * 16 + "┤")
    lines.append("└" + "─" * width + "┘")
    return "\n".join(lines)
