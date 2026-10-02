from __future__ import annotations

from copy import deepcopy
from typing import Any

CURRENT_CONFIG_SCHEMA = 3


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
        if schema == 2:
            migrated.setdefault("continuity", {})
            migrated["continuity"].setdefault("session_summary_items", 3)
            migrated["continuity"].setdefault("correction_context_turns", 6)
            migrated["continuity"].setdefault("memory_half_life_days", 30)
            migrated.setdefault("presence", {})
            migrated["presence"].setdefault("return_window_seconds", 1800)
            migrated.setdefault("proactive", {})
            migrated["proactive"].setdefault("default_ttl_seconds", 86400)
            migrated["proactive"].setdefault("defer_seconds", 300)
            schema = 3
            migrated["schema"] = schema
            changes.append("config schema 2 -> 3: 7.4 continuity and presence defaults")
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
