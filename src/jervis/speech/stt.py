from __future__ import annotations

import threading
import time

import numpy as np


class LazyWhisper:
    def __init__(
        self,
        name: str = "tiny.en",
        device: str = "cpu",
        compute_type: str = "int8",
        unload_seconds: int = 180,
    ) -> None:
        self.name = name
        self.device = device
        self.compute_type = compute_type
        self.unload_seconds = max(30, int(unload_seconds))
        self.model = None
        self.used = 0.0
        self.lock = threading.RLock()

    def _get(self):
        with self.lock:
            if self.model is None:
                from faster_whisper import WhisperModel

                self.model = WhisperModel(
                    self.name,
                    device=self.device,
                    compute_type=self.compute_type,
                )
            self.used = time.monotonic()
            return self.model

    def transcribe(self, samples, language: str = "en") -> str:
        segments, _ = self._get().transcribe(
            np.asarray(samples, dtype=np.float32),
            language=language,
            beam_size=3,
            vad_filter=True,
            condition_on_previous_text=False,
        )
        self.used = time.monotonic()
        return " ".join(segment.text.strip() for segment in segments).strip()

    def maybe_unload(self) -> bool:
        if self.model is None:
            return False
        if time.monotonic() - self.used <= self.unload_seconds:
            return False
        self.model = None
        return True
