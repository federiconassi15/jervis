import re,secrets
from dataclasses import dataclass
from .models import ConfidenceBand
from .security import hash_passphrase,verify_passphrase
@dataclass(slots=True)
class IdentityResult:
    user_id:str|None
    authenticated:bool
    match:object
    needs_retry:bool=False
    needs_auth:bool=False
class IdentityManager:
    def __init__(self,state,sessions,speaker,config):self.state=state;self.sessions=sessions;self.speaker=speaker;self.config=config
    def identify(self,samples,sample_rate):
        active=self.sessions.active();active_user=active.user_id if active else None;match=self.speaker.match(samples,sample_rate,active_user)
        if match.band is ConfidenceBand.STRONG and match.user_id:self.sessions.create(match.user_id,match.score,"voice");self.state.touch_user(match.user_id);return IdentityResult(match.user_id,True,match)
        if match.band is ConfidenceBand.SESSION_ASSISTED and active_user and match.user_id in {None,active_user}:self.sessions.refresh(match.score);return IdentityResult(active_user,True,match)
        if active_user and match.band is ConfidenceBand.UNKNOWN:self.sessions.refresh();return IdentityResult(active_user,True,match)
        if match.band is ConfidenceBand.UNCERTAIN:return IdentityResult(match.user_id,False,match,needs_retry=True)
        return IdentityResult(None,False,match,needs_auth=True)
    def verify_global_passphrase(self,passphrase):
        encoded=self.state.get_kv("auth.passphrase_hash")
        return isinstance(encoded,str) and verify_passphrase(passphrase,encoded)
    def set_global_passphrase(self,passphrase):self.state.set_kv("auth.passphrase_hash",hash_passphrase(passphrase))
    def create_user(self,name,honorific=None,owner=False):
        clean=re.sub(r"[^A-Za-z0-9 _.'-]","",name).strip()
        if not clean:raise ValueError("name cannot be empty")
        row=self.state.user_by_name(clean)
        if row:return str(row["id"])
        uid=secrets.token_hex(8);self.state.upsert_user(uid,clean,honorific,"owner" if owner else "known");return uid
