import platform,shutil,subprocess
class TTS:
    def __init__(self,backend="system",voice="en-GB-RyanNeural"):self.backend=backend;self.voice=voice
    def speak(self,text):
        if not text.strip():return
        if self.backend=="edge" and shutil.which("edge-playback"):
            if subprocess.run(["edge-playback","--voice",self.voice,"--text",text],check=False).returncode==0:return
        system=platform.system()
        if system=="Darwin":subprocess.run(["say",text],check=False);return
        if system=="Windows":
            esc=text.replace("'","''");script="Add-Type -AssemblyName System.Speech;$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"+f"$s.Speak('{esc}')"
            subprocess.run(["powershell","-NoProfile","-NonInteractive","-Command",script],check=False);return
        binary=shutil.which("espeak-ng") or shutil.which("espeak")
        if binary:subprocess.run([binary,text],check=False);return
        raise RuntimeError("no TTS backend found")
