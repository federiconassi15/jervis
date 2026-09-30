from datetime import datetime,time as clock
def _clock(value):h,m=map(int,value.split(":"));return clock(h,m)
class ProactiveEngine:
    def __init__(self,state,config,announce):self.state=state;self.config=config;self.announce=announce;self.last={}
    def quiet_now(self):
        start=_clock(self.config["quiet_hours_start"]);end=_clock(self.config["quiet_hours_end"]);now=datetime.now().time()
        return start<=now<end if start<=end else now>=start or now<end
    def alert(self,key,message,cooldown=900):
        import time
        if not self.config.get("enabled",True) or self.quiet_now():return False
        now=time.time()
        if now-self.last.get(key,0)<cooldown:return False
        self.last[key]=now;self.state.event("proactive_alert",key);self.announce(message);return True
