#!/usr/bin/env python3
from __future__ import annotations

import tempfile
from pathlib import Path

from jervis.config import DEFAULT_CONFIG, load, save
from jervis.security import hash_passphrase, verify_passphrase
from jervis.sessions import SessionManager
from jervis.state import State


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="jervis-smoke-") as directory:
        root = Path(directory)
        config_path = root / "config.json"
        save(config_path, DEFAULT_CONFIG)
        assert load(config_path)["assistant"]["wake_acknowledgement"] == "Boss?"

        state = State(root / "state.sqlite3")
        try:
            state.upsert_user("owner", "Owner", "sir", "owner")
            sessions = SessionManager(state, 60, 30)
            assert sessions.create("owner", 0.99, "smoke").user_id == "owner"
            encoded = hash_passphrase("correct horse battery staple")
            assert verify_passphrase("correct horse battery staple", encoded)
        finally:
            state.close()

    print("Jervis smoke PASS")


if __name__ == "__main__":
    main()
