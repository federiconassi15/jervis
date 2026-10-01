from __future__ import annotations

import os
import shutil
import sys
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


def install_native_copy() -> Path:
    source = Path(sys.executable).resolve()
    target = stable_binary()
    if same_file(source, target):
        return target

    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".new")
    shutil.copy2(source, temporary)
    if os.name != "nt":
        temporary.chmod(0o755)
    os.replace(temporary, target)
    return target


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

    if not already_installed:
        target = install_native_copy()
        os.environ["JERVIS_LAUNCHER_PATH"] = str(target)
        os.environ["JERVIS_INSTALL_ROOT"] = str(install_root())
        cli_main(args or ["install"])
        return

    os.environ.setdefault("JERVIS_LAUNCHER_PATH", str(target))
    os.environ.setdefault("JERVIS_INSTALL_ROOT", str(install_root()))
    cli_main(args)


if __name__ == "__main__":
    main()
