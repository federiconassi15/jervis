import json,shutil,subprocess
from dataclasses import dataclass
@dataclass(slots=True)
class BrainReply:
    ok:bool
    text:str
    error:str=""
class OpenClawBrain:
    def __init__(self,agent="main",timeout=60,thinking="low"):self.agent=agent;self.timeout=int(timeout);self.thinking=thinking
    @property
    def available(self):return shutil.which("openclaw") is not None
    def ask(self,message,session_key):
        if not self.available:return BrainReply(False,"","OpenClaw is not installed")
        cmd=["openclaw","agent","--agent",self.agent,"--session-key",session_key,"--message",message,"--thinking",self.thinking,"--timeout",str(self.timeout),"--json"]
        try:p=subprocess.run(cmd,text=True,capture_output=True,timeout=self.timeout+10,check=False)
        except (OSError,subprocess.TimeoutExpired) as exc:return BrainReply(False,"",str(exc))
        if p.returncode:return BrainReply(False,"",p.stderr.strip() or "OpenClaw command failed")
        try:data=json.loads(p.stdout)
        except json.JSONDecodeError:return BrainReply(False,"","OpenClaw returned invalid JSON")
        text=str(data.get("final") or "") if isinstance(data,dict) else ""
        return BrainReply(bool(text),text,"" if text else "OpenClaw returned no final text")
    def doctor(self):
        if not self.available:return False,"not installed"
        p=subprocess.run(["openclaw","doctor"],text=True,capture_output=True,timeout=60,check=False)
        return p.returncode==0,(p.stdout+p.stderr).strip()[-2000:]
