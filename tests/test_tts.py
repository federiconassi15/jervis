import wave

import numpy as np

from jervis.speech.tts import TTS


def test_resample_changes_length():
    source = np.linspace(-0.5, 0.5, 160, dtype=np.float32)
    target = TTS._resample(source, 16000, 48000)
    assert 478 <= len(target) <= 482


def test_read_wav(tmp_path):
    path = tmp_path / "test.wav"
    samples = (np.linspace(-0.25, 0.25, 160) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16000)
        handle.writeframes(samples.tobytes())
    decoded, rate = TTS._read_wav(path)
    assert rate == 16000
    assert decoded.shape == (160,)
    assert np.max(np.abs(decoded)) <= 0.26
