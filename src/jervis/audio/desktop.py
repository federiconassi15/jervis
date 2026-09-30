import queue
from contextlib import AbstractContextManager
import numpy as np
class DesktopAudio(AbstractContextManager):
    def __init__(self,input_device,output_device,sample_rate=16000,blocksize=480):
        self.input_device=input_device;self.output_device=output_device;self.sample_rate=int(sample_rate);self.blocksize=int(blocksize);self.q=queue.Queue(maxsize=64);self.i=None;self.o=None
    def __enter__(self):
        import sounddevice as sd
        def cb(indata,frames,time_info,status):
            del frames,time_info,status
            x=np.asarray(indata[:,0],dtype=np.float32).copy()
            try:self.q.put_nowait(x)
            except queue.Full:
                try:self.q.get_nowait()
                except queue.Empty:pass
        self.i=sd.InputStream(device=self.input_device,channels=1,samplerate=self.sample_rate,blocksize=self.blocksize,dtype="float32",callback=cb)
        self.o=sd.OutputStream(device=self.output_device,channels=1,samplerate=self.sample_rate,blocksize=self.blocksize,dtype="float32");self.i.start();self.o.start();return self
    def read(self,timeout=2):return self.q.get(timeout=timeout)
    def play(self,samples):self.o.write(np.asarray(samples,dtype=np.float32).reshape(-1,1))
    def __exit__(self,*args):
        for s in (self.i,self.o):
            if s:
                try:s.stop()
                finally:s.close()
        return False
