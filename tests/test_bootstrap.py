from __future__ import annotations

from pathlib import Path

import bootstrap


def test_source_version_reads_patch_line(tmp_path: Path):
    version_file = tmp_path / "src" / "jervis" / "version.py"
    version_file.parent.mkdir(parents=True)
    version_file.write_text('__version__ = "7.1.42"\n', encoding="utf-8")
    assert bootstrap.source_version(tmp_path) == "7.1.42"


def test_source_version_rejects_other_release_lines(tmp_path: Path):
    version_file = tmp_path / "src" / "jervis" / "version.py"
    version_file.parent.mkdir(parents=True)
    version_file.write_text('__version__ = "7.2.0"\n', encoding="utf-8")

    try:
        bootstrap.source_version(tmp_path)
    except RuntimeError as exc:
        assert "7.1.x" in str(exc)
    else:
        raise AssertionError("7.2.0 should not be accepted by the 7.1 bootstrap")
