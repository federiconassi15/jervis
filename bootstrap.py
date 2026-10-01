#!/usr/bin/env python3
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import venv
import zipfile
from contextlib import contextmanager
from pathlib import Path

VERSION = "7.1.1"
MINIMUM_PYTHON = (3, 11)
BLUE = "\033[38;5;45m"
GREEN = "\033[38;5;82m"
RED = "\033[38;5;203m"
RESET = "\033[0m"


def paint(text: str, color: str) -> str:
    return color + text + RESET if sys.stdout.isatty() else text


def install_root() -> Path:
    home = Path.home()
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local")) / "Jervis"
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / "Jervis"
    return Path(os.environ.get("XDG_DATA_HOME", home / ".local" / "share")) / "jervis"


@contextmanager
def source_tree():
    archive = Path(sys.argv[0]).resolve()
    if archive.is_file() and zipfile.is_zipfile(archive):
        with tempfile.TemporaryDirectory(prefix="jervis-release-") as directory:
            with zipfile.ZipFile(archive) as bundle:
                bundle.extractall(directory)
            yield Path(directory)
        return
    yield Path(__file__).resolve().parent


def venv_python(root: Path) -> Path:
    return root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def stable_launcher(root: Path) -> Path:
    return root / "bin" / ("jervis.cmd" if os.name == "nt" else "jervis")


def launcher_bytes(python: Path) -> bytes:
    if os.name == "nt":
        return ('@"' + str(python) + '" -m jervis.cli %*\r\n').encode("utf-8")
    return ('#!/bin/sh\nexec "' + str(python) + '" -m jervis.cli "$@"\n').encode("utf-8")


class Spinner:
    frames = ["◐", "◓", "◑", "◒"]

    def __init__(self, label: str) -> None:
        self.label = label
        self.running = False
        self.thread: threading.Thread | None = None

    def __enter__(self):
        self.running = True
        if sys.stdout.isatty():
            self.thread = threading.Thread(target=self._loop, daemon=True)
            self.thread.start()
        else:
            print(self.label)
        return self

    def _loop(self) -> None:
        index = 0
        while self.running:
            frame = self.frames[index % len(self.frames)]
            print(
                "\r" + paint("  " + frame + "  " + self.label, BLUE),
                end="",
                flush=True,
            )
            index += 1
            time.sleep(0.12)

    def __exit__(self, exc_type, exc, tb):
        self.running = False
        if self.thread:
            self.thread.join(timeout=0.5)
        if sys.stdout.isatty():
            print("\r" + " " * (len(self.label) + 12) + "\r", end="", flush=True)
        if exc_type is None:
            print(paint("  ✓  " + self.label, GREEN))
        return False


def run_logged(command: list[str], log_path: Path, env: dict[str, str] | None = None) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8", errors="replace") as log:
        log.write("\n$ " + subprocess.list2cmdline(command) + "\n")
        log.flush()
        proc = subprocess.run(
            command,
            stdout=log,
            stderr=subprocess.STDOUT,
            env=env,
            check=False,
            text=True,
        )
    if proc.returncode != 0:
        raise RuntimeError("A setup command failed. Details: " + str(log_path))


def main() -> None:
    if sys.version_info < MINIMUM_PYTHON:
        raise SystemExit("Jervis requires Python 3.11 or newer.")

    root = install_root()
    versions = root / "versions"
    logs = root / "logs"
    versions.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    candidate = versions / (VERSION + "-" + stamp + "-" + str(os.getpid()))
    log_path = logs / ("installer-" + stamp + ".log")
    launcher = stable_launcher(root)
    current = root / "CURRENT"

    old_launcher = launcher.read_bytes() if launcher.exists() else None
    old_current = current.read_bytes() if current.exists() else None

    try:
        print()
        print(paint("  J E R V I S  ·  " + VERSION, BLUE))
        print()

        with Spinner("Preparing the installer"):
            venv.EnvBuilder(with_pip=True, clear=False).create(candidate)
            python = venv_python(candidate)
            with source_tree() as source:
                run_logged(
                    [
                        str(python),
                        "-m",
                        "pip",
                        "install",
                        "--disable-pip-version-check",
                        "--no-input",
                        "--upgrade",
                        "pip",
                        "setuptools",
                        "wheel",
                    ],
                    log_path,
                )
                run_logged(
                    [
                        str(python),
                        "-m",
                        "pip",
                        "install",
                        "--disable-pip-version-check",
                        "--no-input",
                        str(source),
                    ],
                    log_path,
                )

        with Spinner("Verifying Jervis"):
            run_logged(
                [
                    str(python),
                    "-c",
                    "import jervis; assert jervis.__version__ == '" + VERSION + "'",
                ],
                log_path,
            )

        launcher.parent.mkdir(parents=True, exist_ok=True)
        temp_launcher = launcher.with_suffix(launcher.suffix + ".tmp")
        temp_launcher.write_bytes(launcher_bytes(python))
        if os.name != "nt":
            temp_launcher.chmod(0o755)
        temp_launcher.replace(launcher)
        current.write_text(candidate.name + "\n", encoding="utf-8")

        env = os.environ.copy()
        env["JERVIS_INSTALL_ROOT"] = str(root)
        env["JERVIS_LAUNCHER_PATH"] = str(launcher)
        env["JERVIS_INSTALL_LOG"] = str(log_path)

        proc = subprocess.run(
            [str(python), "-m", "jervis.cli", "install"],
            env=env,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError("Jervis setup did not finish. Details: " + str(log_path))

    except KeyboardInterrupt:
        print()
        print("Jervis setup cancelled.")
        shutil.rmtree(candidate, ignore_errors=True)
        return
    except Exception as exc:
        launcher.parent.mkdir(parents=True, exist_ok=True)
        if old_launcher is None:
            launcher.unlink(missing_ok=True)
        else:
            launcher.write_bytes(old_launcher)
            if os.name != "nt":
                launcher.chmod(0o755)
        if old_current is None:
            current.unlink(missing_ok=True)
        else:
            current.write_bytes(old_current)
        shutil.rmtree(candidate, ignore_errors=True)
        print()
        print(paint("  ✕  Jervis setup stopped safely", RED))
        print("  " + str(exc))
        return


if __name__ == "__main__":
    main()
