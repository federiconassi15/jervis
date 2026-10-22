from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess

import pytest


@pytest.mark.skipif(os.name == "nt", reason="POSIX shell bootstrap only")
@pytest.mark.parametrize("payload_exit_code", [0, 7])
def test_posix_bootstrap_cleans_downloads_and_preserves_exit_code(
    tmp_path: Path, payload_exit_code: int
):
    """Downloaded executables must not survive either successful or failed setup."""
    bin_dir = tmp_path / "fake-bin"
    bin_dir.mkdir()
    downloader = bin_dir / "curl"
    downloader.write_text(
        "#!/bin/sh\n"
        "while [ \"$#\" -gt 0 ]; do\n"
        "  case \"$1\" in\n"
        "    -o) shift; out=\"$1\" ;;\n"
        "    -*) ;;\n"
        "    *) url=\"$1\" ;;\n"
        "  esac\n"
        "  shift\n"
        "done\n"
        "case \"$url\" in\n"
        "  */SHA256SUMS) cp \"$JERVIS_TEST_SUMS\" \"$out\" ;;\n"
        "  *) cp \"$JERVIS_TEST_BINARY\" \"$out\" ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    downloader.chmod(0o755)
    uname = bin_dir / "uname"
    uname.write_text(
        '#!/bin/sh\ncase "$1" in -s) echo Linux ;; -m) echo x86_64 ;; esac\n',
        encoding="utf-8",
    )
    uname.chmod(0o755)

    payload = tmp_path / "native-payload"
    payload.write_text(f"#!/bin/sh\nexit {payload_exit_code}\n", encoding="utf-8")
    sums = tmp_path / "SHA256SUMS"
    sums.write_text(
        f"{hashlib.sha256(payload.read_bytes()).hexdigest()}  jervis-linux-x64\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env.update(
        TMPDIR=str(tmp_path),
        PATH=str(bin_dir) + os.pathsep + env.get("PATH", ""),
        JERVIS_TEST_SUMS=str(sums),
        JERVIS_TEST_BINARY=str(payload),
    )
    script = Path(__file__).resolve().parents[1] / "install.sh"
    result = subprocess.run(
        ["sh", str(script)], env=env, capture_output=True, text=True, timeout=30
    )

    assert result.returncode == payload_exit_code, result.stderr
    assert not list(tmp_path.glob("jervis-install-*"))
    assert not list(tmp_path.glob("jervis-bootstrap-*.log"))
