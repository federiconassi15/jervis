import plistlib,subprocess
from pathlib import Path
from .base import PlatformAdapter
from ..models import Health
class MacOSPlatform(PlatformAdapter):
    def plist(self):return Path.home()/"Library/LaunchAgents/ai.jervis.runtime.plist"
    def install_service(self,executable,env):
        path=self.plist();path.parent.mkdir(parents=True,exist_ok=True)
        payload={"Label":"ai.jervis.runtime","ProgramArguments":[str(executable),"run"],"RunAtLoad":True,"KeepAlive":{"SuccessfulExit":False},"EnvironmentVariables":env,"StandardOutPath":str(Path.home()/"Library/Logs/jervis.log"),"StandardErrorPath":str(Path.home()/"Library/Logs/jervis-error.log")}
        with path.open("wb") as handle:plistlib.dump(payload,handle)
        subprocess.run(["launchctl","unload",str(path)],check=False);subprocess.run(["launchctl","load",str(path)],check=True)
    def remove_service(self):
        path=self.plist();subprocess.run(["launchctl","unload",str(path)],check=False);path.unlink(missing_ok=True)
    def service_health(self):
        p=subprocess.run(["launchctl","list","ai.jervis.runtime"],text=True,capture_output=True,check=False)
        return Health(p.returncode==0,"service",p.stdout.strip() or p.stderr.strip())
