from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(slots=True)
class AudioQuality:
    rms: float
    clipping: float
    score: float
    label: str


def rms(samples) -> float:
    data = np.asarray(samples, dtype=np.float32)
    if data.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(data * data, dtype=np.float64)))


def clipping_ratio(samples, threshold: float = 0.985) -> float:
    data = np.asarray(samples, dtype=np.float32)
    if data.size == 0:
        return 0.0
    return float(np.mean(np.abs(data) >= threshold))


def quality_score(samples) -> float:
    level = rms(samples)
    clipping = clipping_ratio(samples)
    if level < 0.004:
        return 0.2
    if level > 0.5 or clipping > 0.01:
        return 0.35
    return float(
        max(
            0.0,
            min(
                1.0,
                min(1.0, level / 0.06) * (1.0 - min(0.8, clipping * 20.0)),
            ),
        )
    )


def analyze(samples) -> AudioQuality:
    level = rms(samples)
    clipping = clipping_ratio(samples)
    score = quality_score(samples)
    if clipping > 0.01:
        label = "clipping"
    elif level < 0.004:
        label = "too quiet"
    elif level > 0.5:
        label = "too loud"
    elif score >= 0.75:
        label = "good"
    else:
        label = "usable"
    return AudioQuality(level, clipping, score, label)
