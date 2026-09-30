from jervis.models import Permission
from jervis.permissions import allowed
from jervis.state import State


def test_owner_permissions_require_auth_for_owner_action(tmp_path):
    state = State(tmp_path / "state.sqlite3")
    try:
        state.upsert_user("owner", "Owner", "sir", "owner")
        assert allowed(state, "owner", Permission.KNOWN_USER, False)
        assert allowed(state, "owner", Permission.TRUSTED_USER, False)
        assert not allowed(state, "owner", Permission.OWNER, False)
        assert allowed(state, "owner", Permission.OWNER, True)
        assert allowed(state, "owner", Permission.AUTH_REQUIRED, True)
    finally:
        state.close()


def test_public_requires_no_identity(tmp_path):
    state = State(tmp_path / "state.sqlite3")
    try:
        assert allowed(state, None, Permission.PUBLIC, False)
        assert not allowed(state, None, Permission.KNOWN_USER, False)
    finally:
        state.close()
