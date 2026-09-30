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
    suffix = ".cmd" if os.name == "nt" else ""
    return root / "bin" / ("jervis" + suffix)


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
    stage = versions / (".staging-" + VERSION + "-" + str(os.getpid()))
    final = versions / VERSION
    launcher = stable_launcher(root)
    current = root / "CURRENT"

    old_launcher = launcher.read_bytes() if launcher.exists() else None
    old_current = current.read_bytes() if current.exists() else None
    replaced_final: Path | None = None

    try:
        if stage.exists():
            shutil.rmtree(stage)
        print("Jervis: staging version " + VERSION + "…")
        venv.EnvBuilder(with_pip=True, clear=True).create(stage)
        python = venv_python(stage)

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

        if final.exists():
            replaced_final = versions / (".previous-" + VERSION + "-" + str(int(time.time())))
            final.replace(replaced_final)
        stage.replace(final)
        python = venv_python(final)

        launcher.parent.mkdir(parents=True, exist_ok=True)
        temp_launcher = launcher.with_suffix(launcher.suffix + ".tmp")
        temp_launcher.write_bytes(launcher_bytes(python))
        if os.name != "nt":
            temp_launcher.chmod(0o755)
        temp_launcher.replace(launcher)

        env = os.environ.copy()
        env["JERVIS_INSTALL_ROOT"] = str(root)
        env["JERVIS_LAUNCHER_PATH"] = str(launcher)
        subprocess.run([str(python), "-m", "jervis.cli", "install"], env=env, check=True)

        current.write_text(VERSION + "\n", encoding="utf-8")
        if replaced_final and replaced_final.exists():
            shutil.rmtree(replaced_final, ignore_errors=True)

        print()
        print("Jervis " + VERSION + " installed successfully.")
        print("Launcher: " + str(launcher))
        if launcher.parent.as_posix() not in os.environ.get("PATH", ""):
            print("Add this directory to PATH for the 'jervis' command: " + str(launcher.parent))
    except Exception:
        if final.exists():
            shutil.rmtree(final, ignore_errors=True)
        if replaced_final and replaced_final.exists():
            replaced_final.replace(final)
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
        shutil.rmtree(stage, ignore_errors=True)
        raise


if __name__ == "__main__":
    main()
