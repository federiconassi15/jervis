from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

DEFAULT_CONFIG: dict[str, Any] = {
    "schema": 1,
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
    },
    "privacy": {
        "persist_dialogue": True,
        "persist_raw_audio": False,
        "redact_auth": True,
        "max_dialogue_rows": 2000,
        "max_event_rows": 5000,
    },
    "presence": {
        "enabled": True,
        "timeout_seconds": 300,
    },
    "proactive": {
        "enabled": True,
        "quiet_hours_start": "23:00",
        "quiet_hours_end": "07:00",
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

    presence = config["presence"]
    if int(presence["timeout_seconds"]) < 30:
        raise ValueError("presence.timeout_seconds must be at least 30")

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
    config = (
        deepcopy(DEFAULT_CONFIG)
        if not path.exists()
        else _merge(
            DEFAULT_CONFIG,
            json.loads(path.read_text(encoding="utf-8")),
        )
    )
    validate(config)
    return config


def save(path: Path, config) -> None:
    validate(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temp.replace(path)
