import json,os,platform,random,shutil,subprocess,sys,tempfile,urllib.request
from pathlib import Path
from .audio.devices import default_devices,list_devices
from .config import DEFAULT_CONFIG,save
from .paths import Paths
from .platforms import current_platform
BLUE="\033[38;5;45m";DIM="\033[2m";RESET="\033[0m";GREEN="\033[38;5;82m";YELLOW="\033[38;5;220m";RED="\033[31m"
BANTER=["Jervis, make me like Tony Stank.","Teaching your computer manners.","No arc reactor required.","Deploying questionable amounts of intelligence.","Please do not unplug reality.","One moment, boss.","Installing good decisions. Results may vary.","Turning caffeine into automation."]
def color(text,value):return value+text+RESET if sys.stdout.isatty() else text
def header():
    print(color("╭──────────────────────────────────────────────╮",BLUE));print(color("│                J E R V I S                   │",BLUE));print(color("│         intelligent systems installer        │",BLUE));print(color("╰──────────────────────────────────────────────╯",BLUE));print();print(color("  “"+random.choice(BANTER)+"”",DIM));print()
def choose(prompt,options,default=0):
    print(prompt)
    for i,option in enumerate(options):print("  "+("›" if i==default else " ")+" "+str(i+1)+". "+option)
    while True:
        value=input("Choose ["+str(default+1)+"]: ").strip()
        if not value:return default
        if value.isdigit() and 1<=int(value)<=len(options):return int(value)-1
        print("Enter one of the listed numbers.")
def install_openclaw():
    if shutil.which("openclaw"):print(color("  ✓ OpenClaw detected",GREEN));return
    if choose("OpenClaw is required for Jervis's agentic brain. Install it now?",["Yes","No"])!=0:print(color("  ! OpenClaw skipped.",YELLOW));return
    system=platform.system();print(color("  • Installing OpenClaw quietly…",BLUE))
    if system=="Windows":
        script=urllib.request.urlopen("https://openclaw.ai/install.ps1",timeout=30).read().decode()
        with tempfile.NamedTemporaryFile("w",suffix=".ps1",delete=False,encoding="utf-8") as handle:handle.write(script);path=handle.name
        try:subprocess.run(["powershell","-NoProfile","-ExecutionPolicy","Bypass","-File",path,"-NoOnboard"],check=True,stdout=subprocess.DEVNULL)
        finally:Path(path).unlink(missing_ok=True)
    else:
        script=urllib.request.urlopen("https://openclaw.ai/install.sh",timeout=30).read()
        with tempfile.NamedTemporaryFile("wb",suffix=".sh",delete=False) as handle:handle.write(script);path=handle.name
        try:subprocess.run(["bash",path,"--no-onboard"],check=True,stdout=subprocess.DEVNULL)
        finally:Path(path).unlink(missing_ok=True)
    if not shutil.which("openclaw"):raise RuntimeError("OpenClaw installer completed but CLI is not on PATH")
    print(color("  ✓ OpenClaw installed",GREEN));print("Jervis will now open the required OpenClaw authentication/onboarding step.")
    subprocess.run(["openclaw","onboard","--install-daemon"],check=True)
def pick_audio(config):
    devices=list_devices();inputs=[d for d in devices if d.inputs>0];outputs=[d for d in devices if d.outputs>0];default_input,default_output=default_devices()
    if choose("Microphone source",["Computer microphone","Android phone over ADB"])==1:
        if not shutil.which("adb"):raise RuntimeError("adb is required for Android microphone mode")
        p=subprocess.run(["adb","devices"],text=True,capture_output=True,check=True);serials=[line.split("\t",1)[0] for line in p.stdout.splitlines() if line.endswith("\tdevice")]
        if not serials:raise RuntimeError("no authorized Android device is visible to adb")
        serial=serials[choose("Android device",serials)];config["audio"]["source"]={"kind":"android","device":None,"android_serial":serial}
    else:
        if not inputs:raise RuntimeError("no microphone devices detected")
        default=next((i for i,d in enumerate(inputs) if d.index==default_input),0);device=inputs[choose("Microphone",[d.name+" ("+d.hostapi+")" for d in inputs],default)]
        config["audio"]["source"]={"kind":"desktop","device":device.index,"android_serial":None}
    if not outputs:raise RuntimeError("no speaker/output devices detected")
    default=next((i for i,d in enumerate(outputs) if d.index==default_output),0);config["audio"]["output_device"]=outputs[choose("Output",[d.name+" ("+d.hostapi+")" for d in outputs],default)].index
def install():
    header();system=platform.system()
    if system not in {"Linux","Darwin","Windows"}:raise RuntimeError("unsupported operating system: "+system)
    print(color("  ✓ "+system+" "+platform.release()+" detected",GREEN));print(color("  ✓ "+platform.machine()+" architecture",GREEN));print()
    mode=["desktop","server"][choose("Installation type",["Desktop","Server"])];install_openclaw()
    config=json.loads(json.dumps(DEFAULT_CONFIG));config["install"]["mode"]=mode;pick_audio(config)
    paths=Paths.resolve();paths.ensure();save(paths.config/"config.json",config)
    executable=Path(sys.executable).with_name("jervis.exe" if os.name=="nt" else "jervis")
    if not executable.exists():
        found=shutil.which("jervis")
        if not found:raise RuntimeError("jervis executable is not available after package install")
        executable=Path(found)
    if config["install"]["start_at_boot"]:current_platform().install_service(executable,{"JERVIS_HOME":str(paths.root)})
    print();print(color("  ✓ Jervis configuration written",GREEN));print(color("  ✓ Startup integration configured",GREEN));print();print(color("Jervis is ready. Run jervis doctor to verify the installation.",BLUE))
def main():
    try:install()
    except KeyboardInterrupt:print("\nInstallation cancelled.");raise SystemExit(130)
    except Exception as exc:print(color("\nInstallation failed: "+str(exc),RED));raise SystemExit(1)
