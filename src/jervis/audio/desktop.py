from __future__ import annotations

import collections
import queue
import threading
import time
from contextlib import AbstractContextManager

import numpy as np


class DesktopAudio(AbstractContextManager):
    def __init__(
        self,
        input_device,
        output_device,
        sample_rate: int = 16000,
        blocksize: int = 480,
    ) -> None:
        self.input_device = input_device
        self.output_device = output_device
        self.sample_rate = int(sample_rate)
        self.blocksize = int(blocksize)
        self._frames: collections.deque[np.ndarray] = collections.deque(maxlen=64)
        self._ready = threading.Condition()
        self.input_stream = None

    def __enter__(self):
        import sounddevice as sd

        def callback(indata, frames, time_info, status) -> None:
            del frames, time_info, status
            frame = np.asarray(indata[:, 0], dtype=np.float32).copy()
            with self._ready:
                self._frames.append(frame)
                self._ready.notify()

        self.input_stream = sd.InputStream(
            device=self.input_device,
            channels=1,
            samplerate=self.sample_rate,
            blocksize=self.blocksize,
            dtype="float32",
            callback=callback,
        )
        self.input_stream.start()
        return self

    def read(self, timeout: float = 2.0) -> np.ndarray:
        deadline = time.monotonic() + max(0.0, float(timeout))
        with self._ready:
            while not self._frames:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise queue.Empty
                self._ready.wait(remaining)
            return self._frames.popleft()

    def flush(self) -> None:
        with self._ready:
            self._frames.clear()

    def __exit__(self, *args):
        if self.input_stream is not None:
            try:
                self.input_stream.stop()
            finally:
                self.input_stream.close()
        return False
