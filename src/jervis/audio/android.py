import socket,subprocess,time
from contextlib import AbstractContextManager
import numpy as np
class AndroidAudioSource(AbstractContextManager):
    SOURCE_RATE=44100
    def __init__(self,serial=None,target_rate=16000):self.serial=serial;self.target_rate=int(target_rate);self.sock=None;self.port=None
    def adb(self,*args,check=True):
        return subprocess.run(["adb"]+(["-s",self.serial] if self.serial else [])+list(args),text=True,capture_output=True,check=check)
    def __enter__(self):
        self.adb("start-server")
        if "\tdevice" not in self.adb("devices").stdout:raise RuntimeError("no authorized Android ADB device found")
        self.adb("shell","am","start","fr.dzx.audiosource/.MainActivity",check=False)
        value=self.adb("forward","tcp:0","localabstract:audiosource").stdout.strip()
        if not value.isdigit():raise RuntimeError("ADB did not return a TCP forward port")
        self.port=int(value);deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            try:self.sock=socket.create_connection(("127.0.0.1",self.port),timeout=1);return self
            except OSError:time.sleep(.2)
        raise RuntimeError("could not connect to Android AudioSource")
    def read(self,frames=1323,timeout=2):
        del timeout
        wanted=int(frames)*2;buf=bytearray()
        while len(buf)<wanted:
            chunk=self.sock.recv(wanted-len(buf))
            if not chunk:raise RuntimeError("Android stream disconnected")
            buf.extend(chunk)
        src=np.frombuffer(buf,dtype="<i2").astype(np.float32)/32768
        n=max(1,round(len(src)*self.target_rate/self.SOURCE_RATE))
        return np.interp(np.linspace(0,1,n,endpoint=False),np.linspace(0,1,len(src),endpoint=False),src).astype(np.float32)
    def __exit__(self,*args):
        if self.sock:self.sock.close()
        if self.port:self.adb("forward","--remove",f"tcp:{self.port}",check=False)
        return False
