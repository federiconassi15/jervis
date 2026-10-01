#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import os
from pathlib import Path

import PyInstaller.__main__

ROOT = Path(__file__).resolve().parents[1]
COLLECT = [
    "textual",
    "faster_whisper",
    "ctranslate2",
    "pocketsphinx",
    "sherpa_onnx",
    "sounddevice",
    "edge_tts",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    args = parser.parse_args()

    fast_spec = importlib.util.find_spec("jervis._fast")
    if fast_spec is None or not fast_spec.origin:
        raise SystemExit(
            "native build requires the compiled jervis._fast extension"
        )
    fast_binary = Path(fast_spec.origin)
    if not fast_binary.is_file():
        raise SystemExit(
            "compiled jervis._fast extension is missing: " + str(fast_binary)
        )

    command = [
        "--noconfirm",
        "--clean",
        "--onefile",
        "--name",
        args.name,
        "--paths",
        str(ROOT / "src"),
        "--hidden-import",
        "jervis._fast",
        "--add-binary",
        str(fast_binary) + os.pathsep + "jervis",
    ]
    for package in COLLECT:
        command += ["--collect-all", package]
    command.append(str(ROOT / "scripts" / "native_entry.py"))
    PyInstaller.__main__.run(command)


if __name__ == "__main__":
    main()
