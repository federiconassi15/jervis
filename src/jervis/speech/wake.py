import numpy as np
class WakeDetector:
    def __init__(self,phrase="jervis",sample_rate=16000):self.phrase=phrase.lower();self.sample_rate=sample_rate;self.decoder=None
    def _load(self):
        if self.decoder:return self.decoder
        from pocketsphinx import Decoder
        cfg=Decoder.default_config();cfg.set_string("-keyphrase",self.phrase);cfg.set_float("-kws_threshold",1e-20);cfg.set_int("-samprate",self.sample_rate)
        self.decoder=Decoder(cfg);self.decoder.start_utt();return self.decoder
    def process(self,frame):
        d=self._load();d.process_raw((np.clip(frame,-1,1)*32767).astype("<i2").tobytes(),False,False);h=d.hyp()
        if h and self.phrase in h.hypstr.lower():d.end_utt();d.start_utt();return True
        return False
