from __future__ import annotations

from dataclasses import dataclass

from .audio.devices import list_devices
from .openclaw_setup import doctor as openclaw_doctor
from .openclaw_setup import find_openclaw, install_official
from .prereqs import ensure_linux_audio, ensure_linux_openclaw_tools


@dataclass(slots=True)
class RepairResult:
    component: str
    ok: bool
    detail: str


def repair_audio() -> RepairResult:
    try:
        ensure_linux_audio(lambda _message: True)
        devices = list_devices()
        inputs = sum(1 for device in devices if device.inputs > 0)
        outputs = sum(1 for device in devices if device.outputs > 0)
        if not devices:
            return RepairResult("audio", False, "no audio devices are visible")
        return RepairResult(
            "audio",
            True,
            str(inputs) + " inputs / " + str(outputs) + " outputs visible",
        )
    except Exception as exc:
        return RepairResult("audio", False, str(exc))


def repair_openclaw() -> RepairResult:
    try:
        cli = find_openclaw()
        if cli is None:
            ensure_linux_openclaw_tools()
            cli = install_official(lambda _message: None)
        healthy, detail = openclaw_doctor(cli)
        if healthy:
            return RepairResult("openclaw", True, "doctor passed")
        return RepairResult("openclaw", False, detail or "doctor reported a problem")
    except Exception as exc:
        return RepairResult("openclaw", False, str(exc))


def repair(component: str) -> RepairResult:
    if component == "audio":
        return repair_audio()
    if component == "openclaw":
        return repair_openclaw()
    raise ValueError("unknown repair component: " + component)
