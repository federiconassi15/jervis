from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass

from .audio.devices import list_devices
from .brain import OpenClawBrain
from .models import Health
from .paths import Paths
from .platforms import current_platform


@dataclass(slots=True)
class DoctorReport:
    checks: list[Health]

    @property
    def ok(self) -> bool:
        return all(item.ok for item in self.checks)

    def render(self) -> str:
        return "\n".join(
            ("[OK] " if item.ok else "[FAIL] ")
            + item.component
            + ": "
            + item.detail
            for item in self.checks
        )


def run_doctor() -> DoctorReport:
    checks: list[Health] = []
    paths = Paths.resolve()

    try:
        paths.ensure()
        checks.append(Health(True, "paths", str(paths.root)))
    except Exception as exc:
        checks.append(Health(False, "paths", str(exc)))

    checks.append(
        Health(sys.version_info >= (3, 11), "python", sys.version.split()[0])
    )

    adapter = current_platform()
    capabilities = adapter.capabilities()
    checks.append(
        Health(
            True,
            "platform",
            capabilities.name
            + " | desktop="
            + capabilities.desktop_startup
            + " | server="
            + capabilities.server_startup,
        )
    )

    try:
        devices = list_devices()
        inputs = sum(1 for device in devices if device.inputs > 0)
        outputs = sum(1 for device in devices if device.outputs > 0)
        checks.append(
            Health(
                bool(devices),
                "audio_devices",
                str(inputs) + " inputs / " + str(outputs) + " outputs",
            )
        )
    except Exception as exc:
        checks.append(Health(False, "audio_devices", str(exc)))

    try:
        checks.append(adapter.service_health())
    except Exception as exc:
        checks.append(Health(False, "service", str(exc)))

    openclaw = shutil.which("openclaw")
    checks.append(
        Health(openclaw is not None, "openclaw", openclaw or "missing")
    )
    ok, detail = OpenClawBrain().doctor()
    checks.append(Health(ok, "openclaw_doctor", detail))

    return DoctorReport(checks)
