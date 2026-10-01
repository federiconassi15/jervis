from __future__ import annotations

import ctypes.util
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Callable

Prompt = Callable[[str], bool]


def _run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def _sudo() -> list[str]:
    if os.name == "nt" or getattr(os, "geteuid", lambda: 1)() == 0:
        return []
    sudo = shutil.which("sudo")
    if not sudo:
        raise RuntimeError(
            "administrator privileges are required for this dependency"
        )
    return [sudo]


def portaudio_available() -> bool:
    if platform.system() in {"Windows", "Darwin"}:
        return True
    return ctypes.util.find_library("portaudio") is not None


def linux_tts_available() -> bool:
    if platform.system() != "Linux":
        return True
    return bool(shutil.which("espeak-ng") or shutil.which("espeak"))


def ensure_linux_audio(prompt: Prompt) -> None:
    if platform.system() != "Linux":
        return

    need_portaudio = not portaudio_available()
    need_tts = not linux_tts_available()
    if not need_portaudio and not need_tts:
        return

    missing = []
    if need_portaudio:
        missing.append("PortAudio")
    if need_tts:
        missing.append("espeak-ng fallback TTS")

    if not prompt(
        "Linux prerequisites are missing ("
        + ", ".join(missing)
        + "). Install them now?"
    ):
        raise RuntimeError(
            "Jervis requires the selected Linux audio/TTS prerequisites"
        )

    prefix = _sudo()
    if shutil.which("apt-get"):
        packages = []
        if need_portaudio:
            packages.append("libportaudio2")
        if need_tts:
            packages.append("espeak-ng")
        _run(prefix + ["apt-get", "install", "-y", *packages])
    elif shutil.which("dnf"):
        packages = []
        if need_portaudio:
            packages.append("portaudio")
        if need_tts:
            packages.append("espeak-ng")
        _run(prefix + ["dnf", "install", "-y", *packages])
    elif shutil.which("pacman"):
        packages = []
        if need_portaudio:
            packages.append("portaudio")
        if need_tts:
            packages.append("espeak-ng")
        _run(
            prefix
            + ["pacman", "-S", "--needed", "--noconfirm", *packages]
        )
    elif shutil.which("zypper"):
        packages = []
        if need_portaudio:
            packages.append("portaudio")
        if need_tts:
            packages.append("espeak-ng")
        _run(
            prefix
            + ["zypper", "--non-interactive", "install", *packages]
        )
    elif shutil.which("apk"):
        packages = []
        if need_portaudio:
            packages.append("portaudio")
        if need_tts:
            packages.append("espeak-ng")
        _run(prefix + ["apk", "add", *packages])
    else:
        raise RuntimeError("no supported Linux package manager was found")

    if need_portaudio and not portaudio_available():
        raise RuntimeError(
            "PortAudio installation completed but the library is still unavailable"
        )
    if need_tts and not linux_tts_available():
        raise RuntimeError(
            "fallback TTS installation completed but espeak is still unavailable"
        )


def find_adb() -> Path | None:
    found = shutil.which("adb")
    if found:
        return Path(found)

    candidates: list[Path] = []
    home = Path.home()
    if platform.system() == "Windows":
        local = Path(
            os.environ.get(
                "LOCALAPPDATA",
                home / "AppData" / "Local",
            )
        )
        candidates += [
            local / "Microsoft" / "WinGet" / "Links" / "adb.exe",
            local / "Android" / "Sdk" / "platform-tools" / "adb.exe",
        ]
    elif platform.system() == "Darwin":
        candidates += [
            Path("/opt/homebrew/bin/adb"),
            Path("/usr/local/bin/adb"),
        ]
    else:
        candidates += [
            Path("/usr/bin/adb"),
            Path("/usr/local/bin/adb"),
        ]

    return next((path for path in candidates if path.exists()), None)


def ensure_adb(prompt: Prompt) -> Path:
    existing = find_adb()
    if existing:
        return existing
    if not prompt("Android Platform Tools are missing. Install ADB now?"):
        raise RuntimeError("ADB is required for Android microphone mode")

    system = platform.system()
    if system == "Windows" and shutil.which("winget"):
        _run(
            [
                "winget",
                "install",
                "--id",
                "Google.PlatformTools",
                "--exact",
                "--accept-package-agreements",
                "--accept-source-agreements",
            ]
        )
    elif system == "Darwin" and shutil.which("brew"):
        _run(["brew", "install", "--cask", "android-platform-tools"])
    elif system == "Linux":
        prefix = _sudo()
        if shutil.which("apt-get"):
            _run(prefix + ["apt-get", "install", "-y", "adb"])
        elif shutil.which("dnf"):
            _run(prefix + ["dnf", "install", "-y", "android-tools"])
        elif shutil.which("pacman"):
            _run(
                prefix
                + [
                    "pacman",
                    "-S",
                    "--needed",
                    "--noconfirm",
                    "android-tools",
                ]
            )
        elif shutil.which("zypper"):
            _run(
                prefix
                + [
                    "zypper",
                    "--non-interactive",
                    "install",
                    "android-tools",
                ]
            )
        else:
            raise RuntimeError(
                "no supported package manager can install ADB"
            )
    else:
        raise RuntimeError(
            "install Android Platform Tools manually and rerun Jervis setup"
        )

    result = find_adb()
    if not result:
        raise RuntimeError(
            "ADB installed but is not discoverable in the current session"
        )
    return result
