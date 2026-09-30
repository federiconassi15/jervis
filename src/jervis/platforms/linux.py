import shutil,subprocess
from pathlib import Path
from .base import PlatformAdapter
from ..models import Health
class LinuxPlatform(PlatformAdapter):
    def unit(self):return Path.home()/".config/systemd/user/jervis.service"
    def install_service(self,executable,env):
        if not shutil.which("systemctl"):raise RuntimeError("systemd is required for managed server mode on Linux")
        unit=self.unit();unit.parent.mkdir(parents=True,exist_ok=True)
        envlines="".join('Environment="'+str(k)+"="+str(v).replace('"','\"')+'"\n' for k,v in env.items())
        unit.write_text("[Unit]\nDescription=Jervis voice assistant\nAfter=network-online.target\n\n[Service]\nType=simple\n"+envlines+"ExecStart="+str(executable)+" run\nRestart=on-failure\nRestartSec=3\n\n[Install]\nWantedBy=default.target\n",encoding="utf-8")
        subprocess.run(["systemctl","--user","daemon-reload"],check=True);subprocess.run(["systemctl","--user","enable","--now","jervis.service"],check=True)
    def remove_service(self):
        subprocess.run(["systemctl","--user","disable","--now","jervis.service"],check=False);self.unit().unlink(missing_ok=True);subprocess.run(["systemctl","--user","daemon-reload"],check=False)
    def service_health(self):
        p=subprocess.run(["systemctl","--user","is-active","jervis.service"],text=True,capture_output=True,check=False)
        return Health(p.returncode==0,"service",p.stdout.strip() or p.stderr.strip())
