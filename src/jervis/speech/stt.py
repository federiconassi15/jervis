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
        unload_seconds: int = 900,
        beam_size: int = 1,
    ) -> None:
        self.name = name
        self.device = device
        self.compute_type = compute_type
        self.unload_seconds = max(60, int(unload_seconds))
        self.beam_size = max(1, int(beam_size))
        self.model = None
        self.used = 0.0
        self.lock = threading.RLock()
        self._prewarm_thread: threading.Thread | None = None

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

    def prewarm(self) -> None:
        with self.lock:
            if self.model is not None:
                return
            if self._prewarm_thread is not None and self._prewarm_thread.is_alive():
                return

        def load() -> None:
            try:
                self._get()
            except Exception:
                pass

        self._prewarm_thread = threading.Thread(
            target=load,
            name="jervis-stt-prewarm",
            daemon=True,
        )
        self._prewarm_thread.start()

    def transcribe(self, samples, language: str = "en") -> str:
        data = np.asarray(samples, dtype=np.float32)
        if not data.size:
            return ""
        segments, _ = self._get().transcribe(
            data,
            language=language,
            beam_size=self.beam_size,
            best_of=1,
            temperature=0.0,
            vad_filter=False,
            condition_on_previous_text=False,
            without_timestamps=True,
        )
        self.used = time.monotonic()
        return " ".join(segment.text.strip() for segment in segments).strip()

    def maybe_unload(self) -> bool:
        with self.lock:
            if self.model is None:
                return False
            if time.monotonic() - self.used <= self.unload_seconds:
                return False
            self.model = None
            return True
