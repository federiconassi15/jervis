import threading,time
import numpy as np
class LazyWhisper:
    def __init__(self,name="tiny.en",device="cpu",compute_type="int8"):self.name=name;self.device=device;self.compute_type=compute_type;self.model=None;self.used=0;self.lock=threading.RLock()
    def _get(self):
        with self.lock:
            if self.model is None:
                from faster_whisper import WhisperModel
                self.model=WhisperModel(self.name,device=self.device,compute_type=self.compute_type)
            self.used=time.monotonic();return self.model
    def transcribe(self,samples,language="en"):
        segments,_=self._get().transcribe(np.asarray(samples,dtype=np.float32),language=language,beam_size=3,vad_filter=True,condition_on_previous_text=False)
        self.used=time.monotonic();return " ".join(s.text.strip() for s in segments).strip()
    def maybe_unload(self):
        if self.model is not None and time.monotonic()-self.used>180:self.model=None;return True
        return False
