from __future__ import annotations

import platform
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path

import numpy as np


class TTS:
    def __init__(
        self,
        backend: str = "system",
        voice: str = "en-GB-RyanNeural",
        output_device: int | None = None,
        volume: float = 1.0,
    ) -> None:
        self.backend = backend
        self.voice = voice
        self.output_device = output_device
        self.volume = float(volume)
        self._cache: dict[str, tuple[np.ndarray, int]] = {}

    def set_volume(self, volume: float) -> None:
        self.volume = max(0.05, min(2.0, float(volume)))

    def set_output_device(self, device: int | None) -> None:
        self.output_device = device

    @staticmethod
    def _ps_quote(value: str) -> str:
        return "'" + value.replace("'", "''") + "'"

    def _render_system(self, text: str, path: Path) -> None:
        system = platform.system()
        if system == "Windows":
            script = (
                "Add-Type -AssemblyName System.Speech;"
                "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
                "$s.SetOutputToWaveFile(" + self._ps_quote(str(path)) + ");"
                "$s.Speak(" + self._ps_quote(text) + ");"
                "$s.Dispose();"
            )
            subprocess.run(
                [
                    "powershell",
                    "-NoLogo",
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    script,
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return

        if system == "Darwin":
            subprocess.run(
                [
                    "say",
                    "--file-format=WAVE",
                    "--data-format=LEI16@22050",
                    "-o",
                    str(path),
                    text,
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return

        binary = shutil.which("espeak-ng") or shutil.which("espeak")
        if not binary:
            raise RuntimeError("no system TTS renderer found")
        subprocess.run(
            [binary, "-w", str(path), text],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    @staticmethod
    def _read_wav(path: Path) -> tuple[np.ndarray, int]:
        with wave.open(str(path), "rb") as handle:
            channels = handle.getnchannels()
            width = handle.getsampwidth()
            rate = handle.getframerate()
            raw = handle.readframes(handle.getnframes())

        if width == 1:
            data = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
        elif width == 2:
            data = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
        elif width == 4:
            data = np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648.0
        else:
            raise RuntimeError("unsupported TTS WAV sample width: " + str(width))

        if channels > 1:
            data = data.reshape(-1, channels).mean(axis=1)
        return np.asarray(data, dtype=np.float32), int(rate)

    @staticmethod
    def _resample(samples: np.ndarray, source_rate: int, target_rate: int) -> np.ndarray:
        if source_rate == target_rate or samples.size < 2:
            return samples
        count = max(1, round(samples.size * target_rate / source_rate))
        return np.interp(
            np.linspace(0.0, 1.0, count, endpoint=False),
            np.linspace(0.0, 1.0, samples.size, endpoint=False),
            samples,
        ).astype(np.float32)

    def _render(self, text: str) -> tuple[np.ndarray, int]:
        cached = self._cache.get(text)
        if cached is not None:
            return cached
        with tempfile.TemporaryDirectory(prefix="jervis-tts-") as directory:
            path = Path(directory) / "speech.wav"
            self._render_system(text, path)
            rendered = self._read_wav(path)
        if len(self._cache) >= 64:
            self._cache.clear()
        self._cache[text] = rendered
        return rendered

    def speak(self, text: str) -> None:
        if not text.strip():
            return
        import sounddevice as sd

        samples, source_rate = self._render(text)
        target_rate = source_rate
        try:
            info = sd.query_devices(self.output_device, "output")
            target_rate = int(round(float(info["default_samplerate"])))
        except Exception:
            pass

        samples = self._resample(samples, source_rate, target_rate)
        samples = np.clip(samples * self.volume, -1.0, 1.0)
        sd.play(
            samples,
            samplerate=target_rate,
            device=self.output_device,
            blocking=True,
        )
