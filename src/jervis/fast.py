from __future__ import annotations

import numpy as np

try:
    from ._fast import AdaptiveVad as _RustAdaptiveVad
    from ._fast import analyze as _rust_analyze
    from ._fast import native_version as _native_version
    from ._fast import rms as _rust_rms
except ImportError:
    _RustAdaptiveVad = None
    _rust_analyze = None
    _rust_rms = None
    _native_version = None


NATIVE_AVAILABLE = _rust_analyze is not None


def backend_name() -> str:
    if _native_version is None:
        return "numpy"
    return "rust-" + str(_native_version())


def _array(samples) -> np.ndarray:
    data = np.asarray(samples, dtype=np.float32)
    if data.ndim != 1:
        data = data.reshape(-1)
    return np.ascontiguousarray(data)


def rms(samples) -> float:
    data = _array(samples)
    if not data.size:
        return 0.0
    if _rust_rms is not None:
        return float(_rust_rms(data))
    return float(np.sqrt(np.dot(data.astype(np.float64), data.astype(np.float64)) / data.size))


def analyze_tuple(samples) -> tuple[float, float, float, str]:
    data = _array(samples)
    if not data.size:
        return 0.0, 0.0, 0.0, "too quiet"
    if _rust_analyze is not None:
        level, clipping, score, label = _rust_analyze(data)
        return float(level), float(clipping), float(score), str(label)

    wide = data.astype(np.float64, copy=False)
    level = float(np.sqrt(np.dot(wide, wide) / data.size))
    clipping = float(np.count_nonzero(np.abs(data) >= 0.985) / data.size)
    if level < 0.004:
        score = 0.2
    elif level > 0.5 or clipping > 0.01:
        score = 0.35
    else:
        score = max(
            0.0,
            min(
                1.0,
                min(1.0, level / 0.06) * (1.0 - min(0.8, clipping * 20.0)),
            ),
        )

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
    return level, clipping, float(score), label


class AdaptiveVAD:
    def __init__(self, noise: float = 0.006) -> None:
        self._noise = float(noise)
        self._native = _RustAdaptiveVad(self._noise) if _RustAdaptiveVad is not None else None

    @property
    def noise(self) -> float:
        if self._native is not None:
            return float(self._native.noise)
        return self._noise

    def speech(self, frame) -> bool:
        data = _array(frame)
        if self._native is not None:
            return bool(self._native.speech(data))

        level = rms(data)
        threshold = max(0.008, self._noise * 2.8)
        detected = level >= threshold
        if not detected:
            self._noise = self._noise * 0.97 + level * 0.03
        return detected
