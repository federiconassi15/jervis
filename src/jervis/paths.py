from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_cache_dir, user_config_dir, user_data_dir, user_log_dir


@dataclass(frozen=True, slots=True)
class Paths:
    root: Path
    config: Path
    data: Path
    logs: Path
    cache: Path

    @classmethod
    def resolve(cls) -> "Paths":
        home_override = os.environ.get("JERVIS_HOME")
        if home_override:
            root = Path(home_override).expanduser().resolve()
            return cls(
                root=root,
                config=root / "config",
                data=root / "data",
                logs=root / "logs",
                cache=root / "cache",
            )

        config = Path(
            os.environ.get("JERVIS_CONFIG_HOME")
            or user_config_dir("Jervis", "Jervis")
        ).expanduser()
        data = Path(
            os.environ.get("JERVIS_DATA_HOME")
            or user_data_dir("Jervis", "Jervis")
        ).expanduser()
        logs = Path(
            os.environ.get("JERVIS_LOG_HOME")
            or user_log_dir("Jervis", "Jervis")
        ).expanduser()
        cache = Path(
            os.environ.get("JERVIS_CACHE_HOME")
            or user_cache_dir("Jervis", "Jervis")
        ).expanduser()

        return cls(
            root=data.parent,
            config=config,
            data=data,
            logs=logs,
            cache=cache,
        )

    def ensure(self) -> None:
        for path in (self.config, self.data, self.logs, self.cache):
            path.mkdir(parents=True, exist_ok=True)

    def service_environment(self) -> dict[str, str]:
        return {
            "JERVIS_CONFIG_HOME": str(self.config),
            "JERVIS_DATA_HOME": str(self.data),
            "JERVIS_LOG_HOME": str(self.logs),
            "JERVIS_CACHE_HOME": str(self.cache),
        }
