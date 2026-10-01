from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from .doctor import run_doctor
from .fast import NATIVE_AVAILABLE, backend_name
from .installer import install
from .repair import repair
from .runtime import Runtime
from .tui import run as run_tui
from .updater import check as check_update
from .version import __version__


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="jervis")
    parser.add_argument("--version", action="version", version="%(prog)s " + __version__)
    subparsers = parser.add_subparsers(dest="command")
    for name in ("run", "tui", "doctor", "install", "update-check", "runtime-info"):
        subparsers.add_parser(name)
    repair_parser = subparsers.add_parser("repair")
    repair_parser.add_argument("component", choices=("audio", "openclaw"))

    args = parser.parse_args(argv)
    command = args.command or "tui"

    if command == "run":
        Runtime().run()
    elif command == "tui":
        run_tui()
    elif command == "doctor":
        report = run_doctor()
        print(report.render())
        raise SystemExit(0 if report.ok else 1)
    elif command == "install":
        raise SystemExit(install())
    elif command == "update-check":
        print(json.dumps(asdict(check_update()), indent=2))
    elif command == "runtime-info":
        print(
            json.dumps(
                {
                    "version": __version__,
                    "audio_backend": backend_name(),
                    "native_acceleration": NATIVE_AVAILABLE,
                },
                indent=2,
            )
        )
    elif command == "repair":
        result = repair(args.component)
        print(("[OK] " if result.ok else "[FAIL] ") + result.component + ": " + result.detail)
        raise SystemExit(0 if result.ok else 1)


if __name__ == "__main__":
    main()
