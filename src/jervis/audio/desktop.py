from __future__ import annotations

import queue
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
        self.q: queue.Queue[np.ndarray] = queue.Queue(maxsize=64)
        self.input_stream = None

    def __enter__(self):
        import sounddevice as sd

        def callback(indata, frames, time_info, status) -> None:
            del frames, time_info, status
            frame = np.asarray(indata[:, 0], dtype=np.float32).copy()
            try:
                self.q.put_nowait(frame)
            except queue.Full:
                try:
                    self.q.get_nowait()
                except queue.Empty:
                    pass
                try:
                    self.q.put_nowait(frame)
                except queue.Full:
                    pass

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
        return self.q.get(timeout=timeout)

    def flush(self) -> None:
        while True:
            try:
                self.q.get_nowait()
            except queue.Empty:
                break

    def __exit__(self, *args):
        if self.input_stream is not None:
            try:
                self.input_stream.stop()
            finally:
                self.input_stream.close()
        return False
