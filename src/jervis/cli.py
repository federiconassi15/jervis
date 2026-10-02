from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .acceptance import run_acceptance
from .backup import create_backup, restore_backup
from .benchmark import (
    format_benchmark_history,
    format_report,
    load_benchmark_history,
    main_json,
    run_benchmark,
)
from .diagnostics import create_diagnostics_bundle
from .doctor import run_doctor
from .fast import NATIVE_AVAILABLE, backend_name
from .installer import install
from .openclaw_compat import check_openclaw_compatibility
from .permissions_audit import audit_permissions
from .repair import render_repair_center, repair
from .runtime import Runtime
from .snapshots import create_snapshot, list_snapshots, restore_snapshot
from .status import collect_status, render_status
from .tui import run as run_tui
from .uninstall import uninstall
from .updater import apply_update, check as check_update, rollback_update
from .version import __version__


def _print_repair(result) -> int:
    results = result if isinstance(result, list) else [result]
    for item in results:
        prefix = "[OK] " if item.ok else "[FAIL] "
        suffix = (" · snapshot=" + item.snapshot_id) if item.snapshot_id else ""
        print(prefix + item.component + ": " + item.detail + suffix)
    return 0 if all(item.ok for item in results) else 1


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="jervis")
    parser.add_argument("--version", action="version", version="%(prog)s " + __version__)
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--safe-mode", action="store_true")

    subparsers.add_parser("tui")

    doctor_parser = subparsers.add_parser("doctor")
    doctor_parser.add_argument("--bundle", nargs="?", const="", default=None)

    subparsers.add_parser("install")
    subparsers.add_parser("reinstall")

    uninstall_parser = subparsers.add_parser("uninstall")
    uninstall_parser.add_argument("--purge-data", action="store_true")
    uninstall_parser.add_argument("--remove-binary", action="store_true")

    subparsers.add_parser("update-check")
    update_parser = subparsers.add_parser("update")
    update_parser.add_argument(
        "--rollback",
        nargs="?",
        const="",
        default=None,
        metavar="SNAPSHOT",
    )

    subparsers.add_parser("runtime-info")

    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("--json", action="store_true", dest="as_json")

    repair_parser = subparsers.add_parser("repair")
    repair_parser.add_argument(
        "component",
        choices=("audio", "openclaw", "database", "startup", "models", "permissions", "all"),
    )
    subparsers.add_parser("repair-center")

    benchmark_parser = subparsers.add_parser(
        "benchmark",
        help="Measure local hot paths and summarize recent live turn latency.",
    )
    benchmark_parser.add_argument("--iterations", type=int, default=100)
    benchmark_parser.add_argument("--history", type=int, default=100)
    benchmark_parser.add_argument("--json", action="store_true", dest="as_json")

    benchmark_history_parser = subparsers.add_parser("benchmark-history")
    benchmark_history_parser.add_argument("--json", action="store_true", dest="as_json")

    snapshot_parser = subparsers.add_parser("snapshot")
    snapshot_sub = snapshot_parser.add_subparsers(dest="snapshot_command", required=True)
    snap_create = snapshot_sub.add_parser("create")
    snap_create.add_argument("reason", nargs="?", default="manual")
    snapshot_sub.add_parser("list")
    snap_restore = snapshot_sub.add_parser("restore")
    snap_restore.add_argument("snapshot_id")

    backup_parser = subparsers.add_parser("backup")
    backup_sub = backup_parser.add_subparsers(dest="backup_command", required=True)
    backup_create = backup_sub.add_parser("create")
    backup_create.add_argument("destination", type=Path)
    backup_restore = backup_sub.add_parser("restore")
    backup_restore.add_argument("source", type=Path)

    permissions_parser = subparsers.add_parser("permissions")
    permissions_parser.add_argument("--json", action="store_true", dest="as_json")

    acceptance_parser = subparsers.add_parser("acceptance-test")
    acceptance_parser.add_argument("--json", action="store_true", dest="as_json")

    diagnostics_parser = subparsers.add_parser("diagnostics")
    diagnostics_parser.add_argument("destination", nargs="?", type=Path)

    openclaw_parser = subparsers.add_parser("openclaw-compat")
    openclaw_parser.add_argument("--json", action="store_true", dest="as_json")

    args = parser.parse_args(argv)
    command = args.command or "tui"

    if command == "run":
        Runtime(safe_mode=args.safe_mode).run()
    elif command == "tui":
        run_tui()
    elif command == "doctor":
        report = run_doctor()
        print(report.render())
        if args.bundle is not None:
            destination = Path(args.bundle) if args.bundle else None
            print("Diagnostics: " + str(create_diagnostics_bundle(destination)))
        raise SystemExit(0 if report.ok else 1)
    elif command == "install":
        raise SystemExit(install())
    elif command == "reinstall":
        uninstall(purge_data=False, remove_binary=False)
        raise SystemExit(install())
    elif command == "uninstall":
        snap = uninstall(
            purge_data=args.purge_data,
            remove_binary=args.remove_binary,
        )
        print("Uninstall complete. Rollback snapshot: " + snap.id)
    elif command == "update-check":
        print(json.dumps(asdict(check_update()), indent=2))
    elif command == "update":
        result = (
            rollback_update(args.rollback or None)
            if args.rollback is not None
            else apply_update()
        )
        print(json.dumps(asdict(result), indent=2))
        raise SystemExit(0 if result.ok else 1)
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
    elif command == "status":
        report = collect_status()
        print(json.dumps(report, indent=2) if args.as_json else render_status(report))
    elif command == "benchmark":
        report = run_benchmark(iterations=args.iterations, history=args.history)
        print(main_json(report) if args.as_json else format_report(report))
    elif command == "benchmark-history":
        rows = load_benchmark_history()
        print(json.dumps(rows, indent=2) if args.as_json else format_benchmark_history(rows))
    elif command == "repair":
        raise SystemExit(_print_repair(repair(args.component)))
    elif command == "repair-center":
        print(render_repair_center())
    elif command == "snapshot":
        if args.snapshot_command == "create":
            info = create_snapshot(args.reason)
            print(json.dumps(asdict(info), indent=2))
        elif args.snapshot_command == "list":
            print(json.dumps([asdict(item) for item in list_snapshots()], indent=2))
        elif args.snapshot_command == "restore":
            info = restore_snapshot(args.snapshot_id)
            print("Restored snapshot " + info.id + " from Jervis " + info.version)
    elif command == "backup":
        if args.backup_command == "create":
            print(str(create_backup(args.destination)))
        else:
            restore_backup(args.source)
            print("Backup restored.")
    elif command == "permissions":
        report = audit_permissions()
        print(json.dumps(report, indent=2))
    elif command == "acceptance-test":
        checks = run_acceptance()
        if args.as_json:
            print(json.dumps([asdict(item) for item in checks], indent=2))
        else:
            for item in checks:
                print(("[OK] " if item.ok else "[FAIL] ") + item.name + ": " + item.detail)
        raise SystemExit(0 if all(item.ok for item in checks) else 1)
    elif command == "diagnostics":
        print(str(create_diagnostics_bundle(args.destination)))
    elif command == "openclaw-compat":
        report = check_openclaw_compatibility()
        print(json.dumps(asdict(report), indent=2))
        raise SystemExit(0 if report.installed and report.wizard_rpc else 1)


if __name__ == "__main__":
    main()
