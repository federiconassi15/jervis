from __future__ import annotations

import queue
import socket
import subprocess
import time
from contextlib import AbstractContextManager
from pathlib import Path

import numpy as np

from ..prereqs import find_adb


class AndroidAudioSource(AbstractContextManager):
    SOURCE_RATE = 44100

    def __init__(
        self,
        serial: str | None = None,
        target_rate: int = 16000,
        adb_path: str | None = None,
    ) -> None:
        self.serial = serial
        self.target_rate = int(target_rate)
        self.adb_path = Path(adb_path) if adb_path else find_adb()
        self.sock: socket.socket | None = None
        self.port: int | None = None
        self._resample_axes: dict[int, tuple[np.ndarray, np.ndarray]] = {}

    def adb(self, *args: str, check: bool = True):
        if self.adb_path is None:
            raise RuntimeError("ADB is not installed or discoverable")
        return subprocess.run(
            [str(self.adb_path)]
            + (["-s", self.serial] if self.serial else [])
            + list(args),
            text=True,
            capture_output=True,
            check=check,
        )

    def __enter__(self):
        self.adb("start-server")
        if "\tdevice" not in self.adb("devices").stdout:
            raise RuntimeError("no authorized Android ADB device found")
        self.adb(
            "shell",
            "am",
            "start",
            "fr.dzx.audiosource/.MainActivity",
            check=False,
        )
        value = self.adb(
            "forward",
            "tcp:0",
            "localabstract:audiosource",
        ).stdout.strip()
        if not value.isdigit():
            raise RuntimeError("ADB did not return a TCP forward port")

        self.port = int(value)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                self.sock = socket.create_connection(
                    ("127.0.0.1", self.port),
                    timeout=1,
                )
                self.sock.settimeout(2)
                return self
            except OSError:
                time.sleep(0.2)
        raise RuntimeError("could not connect to Android AudioSource")

    def read(self, frames: int = 1323, timeout: float = 2.0) -> np.ndarray:
        if self.sock is None:
            raise RuntimeError("Android audio source is not connected")

        self.sock.settimeout(max(0.05, float(timeout)))
        wanted = int(frames) * 2
        buffer = bytearray()
        try:
            while len(buffer) < wanted:
                chunk = self.sock.recv(wanted - len(buffer))
                if not chunk:
                    raise RuntimeError("Android stream disconnected")
                buffer.extend(chunk)
        except socket.timeout as exc:
            raise queue.Empty from exc

        source = np.frombuffer(buffer, dtype="<i2").astype(np.float32) / 32768.0
        count = max(
            1,
            round(len(source) * self.target_rate / self.SOURCE_RATE),
        )
        axes = self._resample_axes.get(len(source))
        if axes is None or len(axes[0]) != count:
            axes = (
                np.linspace(0, 1, count, endpoint=False),
                np.linspace(0, 1, len(source), endpoint=False),
            )
            self._resample_axes[len(source)] = axes
        return np.interp(axes[0], axes[1], source).astype(np.float32)

    def flush(self) -> None:
        if self.sock is None:
            return
        previous = self.sock.gettimeout()
        try:
            self.sock.setblocking(False)
            while True:
                try:
                    if not self.sock.recv(65536):
                        break
                except (BlockingIOError, InterruptedError):
                    break
        finally:
            self.sock.settimeout(previous)

    def __exit__(self, *args):
        if self.sock:
            self.sock.close()
        if self.port:
            self.adb(
                "forward",
                "--remove",
                "tcp:" + str(self.port),
                check=False,
            )
        return False
