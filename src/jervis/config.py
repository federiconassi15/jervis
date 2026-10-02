from __future__ import annotations

import json
import os
import time
from copy import deepcopy
from pathlib import Path
from typing import Any

from .migrations import CURRENT_CONFIG_SCHEMA, migrate_config

DEFAULT_CONFIG: dict[str, Any] = {
    "schema": CURRENT_CONFIG_SCHEMA,
    "assistant": {
        "name": "Jervis",
        "wake_word": "jervis",
        "wake_acknowledgement": "Boss?",
        "language": "en",
    },
    "install": {
        "mode": "desktop",
        "start_at_boot": True,
    },
    "audio": {
        "source": {
            "kind": "desktop",
            "device": None,
            "android_serial": None,
        },
        "output_device": None,
        "sample_rate": 16000,
        "channels": 1,
        "jervis_volume": 1.0,
        "aec": False,
        "auto_gain": True,
    },
    "speech": {
        "stt_model": "tiny.en",
        "stt_device": "cpu",
        "compute_type": "int8",
        "follow_up_seconds": 10,
        "tts_backend": "system",
        "edge_voice": "en-GB-RyanNeural",
        "stt_prewarm": True,
        "stt_keep_warm_seconds": 900,
        "stt_beam_size": 1,
        "endpoint_silence_seconds": 0.45,
        "max_command_seconds": 12.0,
    },
    "identity": {
        "enabled": True,
        "trusted_session_seconds": 14400,
        "inactivity_seconds": 1800,
        "strong_threshold": 0.78,
        "session_threshold": 0.68,
        "uncertain_threshold": 0.58,
        "minimum_margin": 0.035,
        "retry_before_auth": True,
        "continuous_learning": True,
        "max_embeddings_per_user": 12,
    },
    "brain": {
        "provider": "openclaw",
        "agent": "main",
        "timeout_seconds": 60,
        "thinking": "low",
        "fast_thinking": "low",
        "default_thinking": "low",
        "deep_thinking": "high",
        "gateway_http": True,
        "gateway_url": "http://127.0.0.1:18789",
        "gateway_retry_seconds": 60,
        "inject_recent_dialogue": False,
        "memory_context_items": 6,
        "memory_context_chars": 1600,
    },
    "privacy": {
        "persist_dialogue": True,
        "persist_raw_audio": False,
        "redact_auth": True,
        "max_dialogue_rows": 2000,
        "max_event_rows": 5000,
    },
    "continuity": {
        "session_summary_items": 3,
        "correction_context_turns": 6,
        "memory_half_life_days": 30,
    },
    "presence": {
        "enabled": True,
        "timeout_seconds": 300,
        "return_window_seconds": 1800,
    },
    "proactive": {
        "enabled": True,
        "quiet_hours_start": "23:00",
        "quiet_hours_end": "07:00",
        "default_ttl_seconds": 86400,
        "defer_seconds": 300,
    },
    "recovery": {
        "auto_snapshot": True,
        "snapshot_keep": 12,
        "crash_recovery": True,
        "safe_mode_after_crashes": 3,
    },
}


def _merge(base, overlay):
    out = deepcopy(base)
    for key, value in overlay.items():
        out[key] = (
            _merge(out[key], value)
            if isinstance(value, dict) and isinstance(out.get(key), dict)
            else value
        )
    return out


def validate(config) -> None:
    if config["install"]["mode"] not in {"desktop", "server"}:
        raise ValueError("install.mode must be desktop or server")

    rate = int(config["audio"]["sample_rate"])
    if not 8000 <= rate <= 96000:
        raise ValueError("audio.sample_rate must be between 8000 and 96000")

    volume = float(config["audio"]["jervis_volume"])
    if not 0.05 <= volume <= 2.0:
        raise ValueError("audio.jervis_volume must be between 0.05 and 2.0")

    speech = config["speech"]
    endpoint = float(speech["endpoint_silence_seconds"])
    if not 0.2 <= endpoint <= 2.0:
        raise ValueError("speech.endpoint_silence_seconds must be between 0.2 and 2.0")

    presence = config["presence"]
    if int(presence["timeout_seconds"]) < 30:
        raise ValueError("presence.timeout_seconds must be at least 30")
    if int(presence["return_window_seconds"]) < int(presence["timeout_seconds"]):
        raise ValueError(
            "presence.return_window_seconds must be >= presence.timeout_seconds"
        )

    continuity = config["continuity"]
    if int(continuity["session_summary_items"]) < 0:
        raise ValueError("continuity.session_summary_items cannot be negative")
    if int(continuity["correction_context_turns"]) < 1:
        raise ValueError("continuity.correction_context_turns must be at least 1")

    identity = config["identity"]
    strong = float(identity["strong_threshold"])
    session = float(identity["session_threshold"])
    uncertain = float(identity["uncertain_threshold"])
    if not 1 >= strong > session > uncertain >= 0:
        raise ValueError(
            "identity thresholds must satisfy "
            "1 >= strong > session > uncertain >= 0"
        )


def load(path: Path):
    if not path.exists():
        config = deepcopy(DEFAULT_CONFIG)
        validate(config)
        return config

    raw = json.loads(path.read_text(encoding="utf-8"))
    migrated, changes = migrate_config(raw)
    config = _merge(DEFAULT_CONFIG, migrated)
    validate(config)
    if changes:
        try:
            from .paths import Paths
            from .snapshots import create_snapshot
            resolved = Paths.resolve()
            if path.resolve() == (resolved.config / "config.json").resolve():
                create_snapshot("pre-config-migration", paths=resolved)
        except Exception:
            pass
        temp = path.with_suffix(path.suffix + ".migrated.tmp")
        temp.write_text(
            json.dumps(config, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temp.replace(path)
    return config


def save(path: Path, config) -> None:
    validate(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and os.environ.get("JERVIS_DISABLE_AUTO_SNAPSHOT") != "1":
        try:
            from .paths import Paths
            from .snapshots import create_snapshot, list_snapshots
            resolved = Paths.resolve()
            if path.resolve() == (resolved.config / "config.json").resolve():
                snapshots = list_snapshots(paths=resolved)
                recent = snapshots[0] if snapshots else None
                if not (
                    recent
                    and recent.reason == "pre-config-edit"
                    and time.time() - recent.created_at < 60
                ):
                    create_snapshot("pre-config-edit", paths=resolved)
        except Exception:
            pass
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temp.replace(path)
