#!/usr/bin/env python3
from __future__ import annotations

import argparse
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

    command = [
        "--noconfirm",
        "--clean",
        "--onefile",
        "--name",
        args.name,
        "--paths",
        str(ROOT / "src"),
    ]
    for package in COLLECT:
        command += ["--collect-all", package]
    command.append(str(ROOT / "scripts" / "native_entry.py"))
    PyInstaller.__main__.run(command)


if __name__ == "__main__":
    main()
