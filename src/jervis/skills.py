import importlib.util
from dataclasses import dataclass
from pathlib import Path
@dataclass(slots=True)
class Skill:
    name:str
    path:Path
    handler:object
class SkillManager:
    def __init__(self,roots):self.roots=roots;self.skills={}
    def discover(self):
        found={}
        for root in self.roots:
            if not root.exists():continue
            for path in root.glob("*/skill.py"):
                name=path.parent.name;spec=importlib.util.spec_from_file_location("jervis_skill_"+name,path)
                if spec is None or spec.loader is None:continue
                module=importlib.util.module_from_spec(spec)
                try:spec.loader.exec_module(module)
                except Exception:continue
                handler=getattr(module,"handle",None)
                if callable(handler):found[name]=Skill(name,path,handler)
        self.skills=found;return found
    def route(self,text,context):
        for skill in self.skills.values():
            try:result=skill.handler(text,context)
            except Exception:continue
            if result:return str(result)
        return None
