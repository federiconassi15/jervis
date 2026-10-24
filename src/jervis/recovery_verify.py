"""Bounded, read-only validation of Jervis snapshot archives."""
from __future__ import annotations

import json
import tarfile
from functools import lru_cache
from pathlib import Path, PurePosixPath

_MAX_MEMBERS = 12000
_MAX_CONTENT = 1024 * 1024 * 1024
_CHUNK = 1024 * 1024


def verify_snapshot_archive(path: Path) -> bool:
    """Verify metadata, path safety, and compressed contents before counting a backup.

    Deliberately never extracts a member. Repeated checks reuse the result for
    the same path, size and modification stamp; archive changes invalidate it.
    """
    try:
        if path.is_symlink() or not path.is_file():
            return False
        stat = path.stat()
        if stat.st_size <= 0 or stat.st_size > _MAX_CONTENT:
            return False
        return _verify_cached(str(path), stat.st_size, stat.st_mtime_ns)
    except (OSError, ValueError):
        return False


@lru_cache(maxsize=64)
def _verify_cached(path: str, size: int, mtime_ns: int) -> bool:
    total = 0
    seen = set()
    found_meta = False
    try:
        with tarfile.open(path, "r:gz") as archive:
            for index, entry in enumerate(archive):
                if index >= _MAX_MEMBERS:
                    return False
                parsed = PurePosixPath(entry.name)
                if (entry.name.startswith("/") or ".." in parsed.parts
                        or not (entry.isdir() or entry.isfile())
                        or entry.name in seen):
                    return False
                seen.add(entry.name)
                if entry.isdir():
                    continue
                if entry.size < 0 or total + entry.size > _MAX_CONTENT:
                    return False
                total += entry.size
                stream = archive.extractfile(entry)
                if stream is None:
                    return False
                with stream:
                    if entry.name == "snapshot.json":
                        if entry.size > 16384:
                            return False
                        metadata = json.loads(stream.read().decode("utf-8"))
                        if not isinstance(metadata, dict):
                            return False
                        identifier = metadata.get("id")
                        if not isinstance(identifier, str) or not identifier:
                            return False
                        if path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1] != identifier + ".tar.gz":
                            return False
                        for required in ("created_at", "reason", "version"):
                            if required not in metadata:
                                return False
                        found_meta = True
                    else:
                        while stream.read(_CHUNK):
                            pass
        return found_meta
    except (OSError, ValueError, EOFError, KeyError, tarfile.TarError, UnicodeError):
        return False
