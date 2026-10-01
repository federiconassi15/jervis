from __future__ import annotations

import numpy as np


class WakeDetector:
    def __init__(self, phrase: str = "jervis", sample_rate: int = 16000) -> None:
        self.phrase = phrase.lower()
        self.sample_rate = sample_rate
        self.decoder = None

    def _load(self):
        if self.decoder is not None:
            return self.decoder

        from pocketsphinx import Decoder

        config = Decoder.default_config()
        config.set_string("-keyphrase", self.phrase)
        config.set_float("-kws_threshold", 1e-20)
        config.set_int("-samprate", self.sample_rate)
        self.decoder = Decoder(config)
        self.decoder.start_utt()
        return self.decoder

    def process(self, frame) -> bool:
        decoder = self._load()
        pcm = (np.clip(frame, -1, 1) * 32767).astype("<i2").tobytes()
        decoder.process_raw(pcm, False, False)
        hypothesis = decoder.hyp()
        if hypothesis and self.phrase in hypothesis.hypstr.lower():
            decoder.end_utt()
            decoder.start_utt()
            return True
        return False
