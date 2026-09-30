import json,re,urllib.request
from dataclasses import dataclass
from .version import VERSION_INFO,__version__
@dataclass(slots=True)
class UpdateInfo:
    available:bool
    current:str
    latest:str|None
    url:str|None
    reason:str
def _version_tuple(value):
    match=re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)",value.strip())
    return None if not match else tuple(map(int,match.groups()))
def check(repo="federiconassi15/jervis"):
    req=urllib.request.Request("https://api.github.com/repos/"+repo+"/releases/latest",headers={"Accept":"application/vnd.github+json","User-Agent":"Jervis-Updater"})
    try:
        with urllib.request.urlopen(req,timeout=10) as response:data=json.loads(response.read().decode())
    except Exception as exc:return UpdateInfo(False,__version__,None,None,"update check failed: "+str(exc))
    latest=_version_tuple(str(data.get("tag_name") or ""))
    if latest is None:return UpdateInfo(False,__version__,None,None,"latest release tag is not semantic version")
    latest_text=".".join(map(str,latest))
    if latest[:2]!=VERSION_INFO[:2]:return UpdateInfo(False,__version__,latest_text,None,"automatic updates never change Jervis major/minor")
    if latest<=VERSION_INFO:return UpdateInfo(False,__version__,latest_text,None,"already current")
    return UpdateInfo(True,__version__,latest_text,str(data.get("html_url") or ""),"patch update available")
