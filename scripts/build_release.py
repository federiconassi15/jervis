#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import shutil
import tempfile
import zipapp
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"


def copy_tree(destination: Path) -> None:
    shutil.copy2(ROOT / "bootstrap.py", destination / "bootstrap.py")
    shutil.copy2(ROOT / "pyproject.toml", destination / "pyproject.toml")
    shutil.copy2(ROOT / "README.md", destination / "README.md")
    shutil.copytree(ROOT / "src", destination / "src")
    (destination / "__main__.py").write_text(
        "from bootstrap import main\nmain()\n", encoding="utf-8"
    )


def main() -> None:
    DIST.mkdir(exist_ok=True)
    output = DIST / "jervis-installer.pyz"
    with tempfile.TemporaryDirectory(prefix="jervis-release-build-") as directory:
        staging = Path(directory)
        copy_tree(staging)
        zipapp.create_archive(staging, output, compressed=True)

    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    (DIST / "jervis-installer.pyz.sha256").write_text(
        digest + "  jervis-installer.pyz\n", encoding="utf-8"
    )
    print(output)
    print(digest)


if __name__ == "__main__":
    main()
