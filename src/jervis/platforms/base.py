from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from ..models import Health


@dataclass(frozen=True, slots=True)
class PlatformCapabilities:
    name: str
    desktop_startup: str
    server_startup: str
    audio_backend: str
    supports_desktop: bool = True
    supports_server: bool = True


class PlatformAdapter(ABC):
    @abstractmethod
    def capabilities(self) -> PlatformCapabilities:
        raise NotImplementedError

    @abstractmethod
    def install_service(
        self,
        executable: Path,
        env: dict[str, str],
        mode: str = "desktop",
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def remove_service(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def service_health(self) -> Health:
        raise NotImplementedError

    def service_installed(self) -> bool:
        """Return whether a managed startup definition exists, active or not."""
        try:
            return bool(self.service_health().ok)
        except Exception:
            return False

    @abstractmethod
    def start_service(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def stop_service(self) -> None:
        raise NotImplementedError

    def restart_service(self) -> None:
        self.stop_service()
        self.start_service()
