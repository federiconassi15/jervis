import json,shutil,subprocess
def openclaw_agents():
    if not shutil.which("openclaw"):return []
    p=subprocess.run(["openclaw","agents","list","--json"],text=True,capture_output=True,timeout=20,check=False)
    if p.returncode:return []
    try:data=json.loads(p.stdout)
    except json.JSONDecodeError:return []
    if isinstance(data,list):return [x for x in data if isinstance(x,dict)]
    if isinstance(data,dict):
        for key in ("agents","items","result"):
            if isinstance(data.get(key),list):return [x for x in data[key] if isinstance(x,dict)]
    return []
