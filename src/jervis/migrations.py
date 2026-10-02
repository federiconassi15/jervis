from __future__ import annotations

from copy import deepcopy
from typing import Any

CURRENT_CONFIG_SCHEMA = 2


def migrate_config(config: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    migrated = deepcopy(config)
    changes: list[str] = []
    schema = int(migrated.get("schema", 1))

    while schema < CURRENT_CONFIG_SCHEMA:
        if schema == 1:
            migrated.setdefault("recovery", {})
            migrated["recovery"].setdefault("auto_snapshot", True)
            migrated["recovery"].setdefault("snapshot_keep", 12)
            migrated["recovery"].setdefault("crash_recovery", True)
            migrated["recovery"].setdefault("safe_mode_after_crashes", 3)
            schema = 2
            migrated["schema"] = schema
            changes.append("config schema 1 -> 2: recovery defaults")
            continue
        raise RuntimeError("no migration path for config schema " + str(schema))

    if schema > CURRENT_CONFIG_SCHEMA:
        raise RuntimeError(
            "config schema "
            + str(schema)
            + " is newer than this Jervis build supports ("
            + str(CURRENT_CONFIG_SCHEMA)
            + ")"
        )

    return migrated, changes
