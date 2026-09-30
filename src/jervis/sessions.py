import secrets,time
from dataclasses import dataclass
@dataclass(slots=True)
class TrustedSession:
    id:str;user_id:str;expires_at:float;refreshed_at:float;confidence:float;source:str
class SessionManager:
    def __init__(self,state,lifetime,inactivity):self.state=state;self.lifetime=int(lifetime);self.inactivity=int(inactivity);self._active=None
    def create(self,user_id,confidence,source):
        now=time.time();self._active=TrustedSession(secrets.token_urlsafe(18),user_id,now+self.lifetime,now,float(confidence),source);self.state.event("trusted_session_created",user_id);return self._active
    def active(self):
        s=self._active
        if not s:return None
        now=time.time()
        if now>=s.expires_at or now-s.refreshed_at>=self.inactivity:self.state.event("trusted_session_expired",s.user_id);self._active=None;return None
        return s
    def refresh(self,confidence=None):
        s=self.active()
        if s:s.refreshed_at=time.time();s.confidence=max(s.confidence,float(confidence)) if confidence is not None else s.confidence
        return s
    def clear(self):self._active=None
