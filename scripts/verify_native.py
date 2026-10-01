#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path


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
    if "7.1.1" not in output:
        raise SystemExit("native verification failed: unexpected version output: " + output)

    print("native verification PASS: " + str(path))


if __name__ == "__main__":
    main()
