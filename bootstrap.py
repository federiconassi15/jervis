#!/usr/bin/env python3
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
import venv
import zipfile
from contextlib import contextmanager
from pathlib import Path

VERSION = "7.1.0"
MINIMUM_PYTHON = (3, 11)


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


def main() -> None:
    if sys.version_info < MINIMUM_PYTHON:
        raise SystemExit("Jervis requires Python 3.11 or newer.")

    root = install_root()
    versions = root / "versions"
    versions.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    candidate = versions / (VERSION + "-" + stamp + "-" + str(os.getpid()))
    launcher = stable_launcher(root)
    current = root / "CURRENT"

    old_launcher = launcher.read_bytes() if launcher.exists() else None
    old_current = current.read_bytes() if current.exists() else None

    try:
        print("Jervis: staging version " + VERSION + "…")
        venv.EnvBuilder(with_pip=True, clear=False).create(candidate)
        python = venv_python(candidate)

        with source_tree() as source:
            subprocess.run(
                [str(python), "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"],
                check=True,
            )
            subprocess.run([str(python), "-m", "pip", "install", str(source)], check=True)

        subprocess.run(
            [str(python), "-c", "import jervis; assert jervis.__version__ == '" + VERSION + "'"],
            check=True,
        )
        subprocess.run([str(python), "-m", "jervis.cli", "--version"], check=True)

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
        subprocess.run([str(python), "-m", "jervis.cli", "install"], env=env, check=True)

        print()
        print("Jervis " + VERSION + " installed successfully.")
        print("Launcher: " + str(launcher))
        path_parts = [Path(p).resolve() for p in os.environ.get("PATH", "").split(os.pathsep) if p]
        if launcher.parent.resolve() not in path_parts:
            print("Add this directory to PATH for the jervis command: " + str(launcher.parent))
    except Exception:
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
        raise


if __name__ == "__main__":
    main()
