#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def source_version() -> str:
    text = (ROOT / "src" / "jervis" / "version.py").read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', text)
    if not match:
        raise SystemExit("native verification failed: source version is unreadable")
    return match.group(1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", required=True)
    args = parser.parse_args()

    path = Path(args.path)
    if os.name == "nt" and path.suffix.lower() != ".exe":
        path = path.with_suffix(".exe")
    if not path.is_file():
        raise SystemExit("native verification failed: missing " + str(path))

    proc = subprocess.run(
        [str(path.resolve()), "--version"],
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )
    output = (proc.stdout + proc.stderr).strip()
    if proc.returncode != 0:
        raise SystemExit("native verification failed: " + output)
    expected_version = source_version()
    if expected_version not in output:
        raise SystemExit(
            "native verification failed: expected "
            + expected_version
            + " in version output: "
            + output
        )

    help_proc = subprocess.run(
        [str(path.resolve()), "--help"],
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )
    help_output = (help_proc.stdout + help_proc.stderr).strip()
    if help_proc.returncode != 0:
        raise SystemExit("native verification failed during --help: " + help_output)
    if "usage:" not in help_output.lower() or "jervis" not in help_output.lower():
        raise SystemExit("native verification failed: unexpected --help output: " + help_output)

    print("native verification PASS: " + str(path))


if __name__ == "__main__":
    main()
