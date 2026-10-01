from __future__ import annotations

import ctypes.util
import os
import platform
import shutil
import subprocess
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable

from .paths import Paths

Prompt = Callable[[str], bool]


def _run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def _sudo() -> list[str]:
    if os.name == "nt" or getattr(os, "geteuid", lambda: 1)() == 0:
        return []
    sudo = shutil.which("sudo")
    if not sudo:
        raise RuntimeError(
            "administrator privileges are required for this Linux dependency"
        )
    return [sudo]


def _linux_install(packages: list[str]) -> None:
    prefix = _sudo()
    if shutil.which("apt-get"):
        _run(prefix + ["apt-get", "update"])
        _run(prefix + ["apt-get", "install", "-y", *packages])
    elif shutil.which("dnf"):
        _run(prefix + ["dnf", "install", "-y", *packages])
    elif shutil.which("pacman"):
        _run(prefix + ["pacman", "-S", "--needed", "--noconfirm", *packages])
    elif shutil.which("zypper"):
        _run(prefix + ["zypper", "--non-interactive", "install", *packages])
    elif shutil.which("apk"):
        _run(prefix + ["apk", "add", *packages])
    else:
        raise RuntimeError("no supported Linux package manager was found")


def ensure_linux_openclaw_tools() -> None:
    if platform.system() != "Linux" or shutil.which("curl"):
        return
    if shutil.which("apt-get"):
        _linux_install(["curl", "ca-certificates"])
    elif shutil.which("dnf") or shutil.which("pacman") or shutil.which("zypper") or shutil.which("apk"):
        _linux_install(["curl", "ca-certificates"])
    if not shutil.which("curl"):
        raise RuntimeError("curl is required by the official OpenClaw Linux installer")


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
        raise RuntimeError("Jervis requires the selected Linux audio/TTS prerequisites")

    if shutil.which("apt-get"):
        packages = []
        if need_portaudio:
            packages.append("libportaudio2")
        if need_tts:
            packages.append("espeak-ng")
        _linux_install(packages)
    elif shutil.which("dnf") or shutil.which("pacman") or shutil.which("zypper"):
        packages = []
        if need_portaudio:
            packages.append("portaudio")
        if need_tts:
            packages.append("espeak-ng")
        _linux_install(packages)
    elif shutil.which("apk"):
        packages = []
        if need_portaudio:
            packages.append("portaudio")
        if need_tts:
            packages.append("espeak-ng")
        _linux_install(packages)
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


def _portable_adb() -> Path:
    suffix = "adb.exe" if os.name == "nt" else "adb"
    return Paths.resolve().data / "tools" / "platform-tools" / suffix


def find_adb() -> Path | None:
    found = shutil.which("adb")
    if found:
        return Path(found)

    portable = _portable_adb()
    if portable.exists():
        return portable

    home = Path.home()
    candidates: list[Path] = []
    if platform.system() == "Windows":
        local = Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local"))
        candidates += [
            local / "Microsoft" / "WinGet" / "Links" / "adb.exe",
            local / "Android" / "Sdk" / "platform-tools" / "adb.exe",
        ]
    elif platform.system() == "Darwin":
        candidates += [Path("/opt/homebrew/bin/adb"), Path("/usr/local/bin/adb")]
    else:
        candidates += [Path("/usr/bin/adb"), Path("/usr/local/bin/adb")]

    return next((path for path in candidates if path.exists()), None)


def _download_platform_tools() -> Path:
    system = platform.system()
    if system == "Windows":
        url = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"
    elif system == "Darwin":
        url = "https://dl.google.com/android/repository/platform-tools-latest-darwin.zip"
    elif system == "Linux" and platform.machine().lower() in {"x86_64", "amd64"}:
        url = "https://dl.google.com/android/repository/platform-tools-latest-linux.zip"
    else:
        raise RuntimeError(
            "Google does not provide a portable Platform Tools archive for this platform"
        )

    tools = Paths.resolve().data / "tools"
    tools.mkdir(parents=True, exist_ok=True)
    archive = tools / "platform-tools.zip"
    request = urllib.request.Request(url, headers={"User-Agent": "Jervis/7.1"})
    with urllib.request.urlopen(request, timeout=120) as response:
        archive.write_bytes(response.read())

    destination = tools / "platform-tools"
    if destination.exists():
        shutil.rmtree(destination)
    with zipfile.ZipFile(archive) as bundle:
        bundle.extractall(tools)
    archive.unlink(missing_ok=True)

    adb = _portable_adb()
    if not adb.exists():
        raise RuntimeError("Android Platform Tools downloaded but adb is missing")
    if os.name != "nt":
        for tool in destination.iterdir():
            if tool.is_file():
                try:
                    tool.chmod(tool.stat().st_mode | 0o111)
                except OSError:
                    pass
    return adb


def ensure_adb(prompt: Prompt) -> Path:
    existing = find_adb()
    if existing:
        return existing
    if not prompt("Android Platform Tools are missing. Install ADB now?"):
        raise RuntimeError("ADB is required for Android microphone mode")

    system = platform.system()
    if system in {"Windows", "Darwin"}:
        return _download_platform_tools()

    if system == "Linux":
        try:
            if shutil.which("apt-get"):
                _linux_install(["adb"])
            elif shutil.which("dnf") or shutil.which("pacman") or shutil.which("zypper"):
                package = "android-tools"
                _linux_install([package])
            elif shutil.which("apk"):
                _linux_install(["android-tools"])
        except (RuntimeError, subprocess.CalledProcessError):
            pass

        result = find_adb()
        if result:
            return result

        return _download_platform_tools()

    raise RuntimeError("Android Platform Tools are not supported on this operating system")
