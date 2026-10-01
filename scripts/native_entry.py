from __future__ import annotations

import os
import shutil
import sys
import time
from pathlib import Path


def install_root() -> Path:
    home = Path.home()
    override = os.environ.get("JERVIS_INSTALL_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local")) / "Jervis"
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / "Jervis"
    return Path(os.environ.get("XDG_DATA_HOME", home / ".local" / "share")) / "jervis"


def stable_binary() -> Path:
    suffix = ".exe" if os.name == "nt" else ""
    return install_root() / "bin" / ("jervis" + suffix)


def same_file(left: Path, right: Path) -> bool:
    try:
        return left.exists() and right.exists() and os.path.samefile(left, right)
    except OSError:
        return left.resolve() == right.resolve()


def install_native_copy(source: Path, target: Path) -> Path | None:
    """Install source at target and return a rollback backup when one existed."""
    target.parent.mkdir(parents=True, exist_ok=True)
    backup: Path | None = None
    if target.exists():
        backup = target.with_name(
            target.name + ".previous-" + str(os.getpid()) + "-" + str(int(time.time()))
        )
        shutil.copy2(target, backup)

    temporary = target.with_name(target.name + ".new-" + str(os.getpid()))
    try:
        shutil.copy2(source, temporary)
        if os.name != "nt":
            temporary.chmod(0o755)
        os.replace(temporary, target)
    except Exception:
        temporary.unlink(missing_ok=True)
        if backup is not None:
            backup.unlink(missing_ok=True)
        raise
    return backup


def rollback_native_copy(target: Path, backup: Path | None) -> None:
    """Restore the previous native launcher, or remove a failed first install."""
    if backup is None:
        target.unlink(missing_ok=True)
        return
    temporary = target.with_name(target.name + ".rollback-" + str(os.getpid()))
    shutil.copy2(backup, temporary)
    if os.name != "nt":
        temporary.chmod(0o755)
    os.replace(temporary, target)
    backup.unlink(missing_ok=True)


def commit_native_copy(backup: Path | None) -> None:
    if backup is not None:
        backup.unlink(missing_ok=True)


def _exit_code(exc: SystemExit) -> int:
    if exc.code is None:
        return 0
    if isinstance(exc.code, int):
        return exc.code
    return 1


def main() -> None:
    from jervis.cli import main as cli_main

    args = sys.argv[1:]
    if "--version" in args or "-h" in args or "--help" in args:
        cli_main(args)
        return

    if not getattr(sys, "frozen", False):
        cli_main(args or ["install"])
        return

    source = Path(sys.executable).resolve()
    target = stable_binary()
    already_installed = same_file(source, target)

    if already_installed:
        os.environ.setdefault("JERVIS_LAUNCHER_PATH", str(target))
        os.environ.setdefault("JERVIS_INSTALL_ROOT", str(install_root()))
        cli_main(args)
        return

    backup = install_native_copy(source, target)
    os.environ["JERVIS_LAUNCHER_PATH"] = str(target)
    os.environ["JERVIS_INSTALL_ROOT"] = str(install_root())
    try:
        cli_main(args or ["install"])
    except SystemExit as exc:
        if _exit_code(exc) == 0:
            commit_native_copy(backup)
        else:
            rollback_native_copy(target, backup)
        raise
    except BaseException:
        rollback_native_copy(target, backup)
        raise
    else:
        commit_native_copy(backup)


if __name__ == "__main__":
    main()
