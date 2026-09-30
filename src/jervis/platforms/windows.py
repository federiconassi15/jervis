import subprocess
from .base import PlatformAdapter
from ..models import Health
class WindowsPlatform(PlatformAdapter):
    task_name="Jervis Voice Assistant"
    def install_service(self,executable,env):
        del env
        command='"'+str(executable)+'" run'
        subprocess.run(["schtasks","/Create","/F","/SC","ONLOGON","/TN",self.task_name,"/TR",command],check=True)
        subprocess.run(["schtasks","/Run","/TN",self.task_name],check=False)
    def remove_service(self):subprocess.run(["schtasks","/Delete","/F","/TN",self.task_name],check=False)
    def service_health(self):
        p=subprocess.run(["schtasks","/Query","/TN",self.task_name],text=True,capture_output=True,check=False)
        return Health(p.returncode==0,"service",p.stdout.strip() or p.stderr.strip())
