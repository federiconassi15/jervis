from dataclasses import dataclass
from .models import Health
@dataclass(slots=True)
class Check:
    name:str
    probe:object
    repair:object=None
class Resilience:
    def __init__(self):self.checks=[];self.failures={}
    def add(self,check):self.checks.append(check)
    def run_once(self):
        results=[]
        for check in self.checks:
            try:health=check.probe()
            except Exception as exc:health=Health(False,check.name,str(exc))
            results.append(health)
            if health.ok:self.failures[check.name]=0;continue
            count=self.failures.get(check.name,0)+1;self.failures[check.name]=count
            if count>=3 and check.repair is not None:
                try:
                    if check.repair():self.failures[check.name]=0
                except Exception:pass
        return results
