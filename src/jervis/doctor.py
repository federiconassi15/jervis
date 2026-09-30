import shutil,sys
from dataclasses import dataclass
from .audio.devices import list_devices
from .brain import OpenClawBrain
from .models import Health
from .paths import Paths
from .platforms import current_platform
@dataclass(slots=True)
class DoctorReport:
    checks:list
    @property
    def ok(self):return all(x.ok for x in self.checks)
    def render(self):return "\n".join(("[OK] " if x.ok else "[FAIL] ")+x.component+": "+x.detail for x in self.checks)
def run_doctor():
    checks=[];paths=Paths.resolve()
    try:paths.ensure();checks.append(Health(True,"paths",str(paths.root)))
    except Exception as exc:checks.append(Health(False,"paths",str(exc)))
    checks.append(Health(sys.version_info>=(3,11),"python",sys.version.split()[0]))
    checks.append(Health(shutil.which("openclaw") is not None,"openclaw",shutil.which("openclaw") or "missing"))
    try:checks.append(Health(bool(list_devices()),"audio_devices","detected"))
    except Exception as exc:checks.append(Health(False,"audio_devices",str(exc)))
    try:checks.append(current_platform().service_health())
    except Exception as exc:checks.append(Health(False,"service",str(exc)))
    ok,detail=OpenClawBrain().doctor();checks.append(Health(ok,"openclaw_doctor",detail))
    return DoctorReport(checks)
