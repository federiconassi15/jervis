from __future__ import annotations

from pathlib import Path


class InstallTransaction:
    def __init__(self, platform_adapter) -> None:
        self.platform = platform_adapter
        self.files: dict[Path, bytes | None] = {}
        self.service_was_active = False
        self.service_changed = False
        self.committed = False

    def __enter__(self):
        try:
            self.service_was_active = bool(self.platform.service_health().ok)
        except Exception:
            self.service_was_active = False
        return self

    def track_file(self, path: Path) -> None:
        if path not in self.files:
            self.files[path] = path.read_bytes() if path.exists() else None

    def mark_service_changed(self) -> None:
        self.service_changed = True

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        if self.service_changed and not self.service_was_active:
            try:
                self.platform.remove_service()
            except Exception:
                pass
        for path, data in self.files.items():
            try:
                if data is None:
                    path.unlink(missing_ok=True)
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(data)
            except Exception:
                pass

    def __exit__(self, exc_type, exc, tb):
        if exc_type is not None or not self.committed:
            self.rollback()
        return False
