"""Private, opt-in incremental text index backed by SQLite FTS5.

No directory is indexed automatically. Symlinks are never traversed, indexing is
bounded, and all queries are restricted to one owner-approved root. Documents
are untrusted content, never executable instructions or tool capabilities.
"""
from __future__ import annotations

import hashlib
import os
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

_ALLOWED_SUFFIXES = frozenset({".txt", ".md", ".rst", ".py", ".json", ".csv"})
_MAX_DOC_BYTES = 1024 * 1024
_MAX_INDEX_BYTES = 128 * 1024 * 1024
_MAX_DOCS = 2000


@dataclass(frozen=True)
class KnowledgeHit:
    path: str
    excerpt: str
    rank: float


class KnowledgeVault:
    def __init__(self, database: Path, root: Path):
        original = Path(root).expanduser()
        if original.is_symlink() or not original.is_dir():
            raise ValueError("Knowledge root must be an existing real directory")
        self.root = original.resolve(strict=True)
        db = Path(database)
        if db.is_symlink():
            raise PermissionError("Knowledge database cannot be a symlink")
        db.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not db.exists():
            fd = os.open(db, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
        if os.name != "nt":
            db.chmod(0o600)
        self.db = sqlite3.connect(db)
        try:
            self.db.execute("CREATE TABLE IF NOT EXISTS identity(root TEXT PRIMARY KEY)")
            previous = self.db.execute("SELECT root FROM identity LIMIT 1").fetchone()
            if previous and previous[0] != str(self.root):
                raise ValueError("Knowledge vault belongs to a different root")
            if not previous:
                self.db.execute("INSERT INTO identity VALUES(?)", (str(self.root),))
            self.db.execute(
                "CREATE TABLE IF NOT EXISTS files(path TEXT PRIMARY KEY, digest TEXT NOT NULL)"
            )
            self.db.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS documents USING fts5("
                "path UNINDEXED, content, tokenize='unicode61')"
            )
            self.db.commit()
        except BaseException:
            self.db.close()
            raise

    def _candidates(self):
        count = 0
        total = 0
        for folder, dirs, files in os.walk(self.root, followlinks=False):
            dirs[:] = sorted(name for name in dirs
                             if not (Path(folder) / name).is_symlink())
            for filename in sorted(files):
                path = Path(folder) / filename
                if path.is_symlink() or path.suffix.lower() not in _ALLOWED_SUFFIXES:
                    continue
                resolved = path.resolve(strict=False)
                if not resolved.is_relative_to(self.root) or not resolved.is_file():
                    continue
                size = path.stat().st_size
                if size > _MAX_DOC_BYTES:
                    continue
                count += 1
                total += size
                if count > _MAX_DOCS or total > _MAX_INDEX_BYTES:
                    raise ValueError("Knowledge vault indexing limits exceeded")
                yield path

    def update(self) -> dict[str, int]:
        """Incremental index; never reads outside the approved root."""
        seen = set()
        added = 0
        for path in self._candidates():
            name = path.relative_to(self.root).as_posix()
            # No symlink traversal on platforms that implement O_NOFOLLOW.
            fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            with os.fdopen(fd, "rb") as handle:
                data = handle.read(_MAX_DOC_BYTES + 1)
            if len(data) > _MAX_DOC_BYTES or b"\x00" in data:
                continue
            try:
                content = data.decode("utf-8")
            except UnicodeDecodeError:
                continue
            digest = hashlib.sha256(data).hexdigest()
            seen.add(name)
            previous = self.db.execute(
                "SELECT digest FROM files WHERE path=?", (name,)
            ).fetchone()
            if previous and previous[0] == digest:
                continue
            self.db.execute("DELETE FROM documents WHERE path=?", (name,))
            self.db.execute(
                "INSERT INTO documents(path,content) VALUES(?,?)", (name, content)
            )
            self.db.execute(
                "INSERT INTO files(path,digest) VALUES(?,?) "
                "ON CONFLICT(path) DO UPDATE SET digest=excluded.digest",
                (name, digest),
            )
            added += 1
        known = {r[0] for r in self.db.execute("SELECT path FROM files")}
        removed = known - seen
        for name in removed:
            self.db.execute("DELETE FROM documents WHERE path=?", (name,))
            self.db.execute("DELETE FROM files WHERE path=?", (name,))
        self.db.commit()
        return {"updated": added, "removed": len(removed), "indexed": len(seen)}

    def search(self, query: str, *, limit: int = 8) -> list[KnowledgeHit]:
        if not 1 <= limit <= 30:
            raise ValueError("Invalid retrieval limit")
        # Treat the query as data, never arbitrary FTS syntax or SQL.
        terms = re.findall(r"[\w]{2,}", query.casefold())[:12]
        if not terms:
            return []
        expression = " AND ".join('"' + word.replace('"', "") + '"' for word in terms)
        rows = self.db.execute(
            "SELECT path, snippet(documents,1,'','','...',16), bm25(documents)"
            " FROM documents WHERE documents MATCH ? ORDER BY bm25(documents) LIMIT ?",
            (expression, limit),
        )
        return [KnowledgeHit(str(p), str(excerpt), float(rank))
                for p, excerpt, rank in rows]

    def close(self):
        self.db.close()
