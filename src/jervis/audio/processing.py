from __future__ import annotations

from dataclasses import dataclass

from ..fast import analyze_tuple, rms


@dataclass(slots=True)
class AudioQuality:
    rms: float
    clipping: float
    score: float
    label: str


def clipping_ratio(samples, threshold: float = 0.985) -> float:
    if threshold == 0.985:
        return analyze_tuple(samples)[1]

    import numpy as np

    data = np.asarray(samples, dtype=np.float32)
    if data.size == 0:
        return 0.0
    return float(np.count_nonzero(np.abs(data) >= threshold) / data.size)


def quality_score(samples) -> float:
    return analyze_tuple(samples)[2]


def analyze(samples) -> AudioQuality:
    level, clipping, score, label = analyze_tuple(samples)
    return AudioQuality(level, clipping, score, label)
