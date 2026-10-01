from __future__ import annotations

from ..audio.processing import rms


class AdaptiveVAD:
    def __init__(self) -> None:
        self.noise = 0.006

    def speech(self, frame) -> bool:
        level = rms(frame)
        threshold = max(0.008, self.noise * 2.8)
        detected = level >= threshold
        if not detected:
            self.noise = self.noise * 0.97 + level * 0.03
        return detected
