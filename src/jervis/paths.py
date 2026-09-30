from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path
from platformdirs import user_config_dir,user_data_dir,user_log_dir

@dataclass(frozen=True,slots=True)
class Paths:
    root: Path
    config: Path
    data: Path
    logs: Path
    cache: Path

    @classmethod
    def resolve(cls):
        override=os.environ.get("JERVIS_HOME")
        if override:
            root=Path(override).expanduser().resolve()
            return cls(root,root/"config",root/"data",root/"logs",root/"cache")
        config=Path(user_config_dir("Jervis","Jervis"))
        data=Path(user_data_dir("Jervis","Jervis"))
        logs=Path(user_log_dir("Jervis","Jervis"))
        return cls(data.parent,config,data,logs,data/"cache")

    def ensure(self):
        for p in (self.config,self.data,self.logs,self.cache):
            p.mkdir(parents=True,exist_ok=True)
