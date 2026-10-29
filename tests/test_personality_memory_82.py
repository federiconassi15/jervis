"""Memory conflict and personality policy tests."""
import pytest

from jervis.capabilities import Principal
from jervis.evolve import resolve_offline
from jervis.local_dialogue import DialogueMemory
from jervis.memory_editor import apply_explicit, delete_explicit, preview
from jervis.persona_profile import Persona, PersonaStore, compose_with_persona
from jervis.state import State


def test_explicit_memories_are_scoped_and_conflicts_require_approval(tmp_path):
    state = State(tmp_path / "state.sqlite3")
    try:
        state.upsert_user("u1", "Alex", "sir", "owner")
        state.upsert_user("u2", "Sam", None, "known")
        alex = Principal("u1", "owner", True)
        sam = Principal("u2", "known", True)
        assert preview(state, alex, "favorite_game", "Skyrim").action == "insert"
        apply_explicit(state, alex, "favorite_game", "Skyrim")
        assert preview(state, alex, "favorite_game", "Skyrim").action == "unchanged"
        assert preview(state, alex, "favorite_game", "Subnautica").action == "conflict"
        with pytest.raises(PermissionError):
            apply_explicit(state, alex, "favorite_game", "Subnautica")
        assert state.memory("u1", "favorite_game") == "Skyrim"
        apply_explicit(state, alex, "favorite_game", "Subnautica",
                       approve_conflict=True)
        assert state.memory("u1", "favorite_game") == "Subnautica"
        assert state.memory("u2", "favorite_game") is None
        with pytest.raises(PermissionError):
            preview(state, Principal("u1", "owner", True, "phone"), "private", "secret")
        delete_explicit(state, alex, "favorite_game")
        assert state.memory("u1", "favorite_game") is None
        assert preview(state, sam, "favorite_game", "Different").action == "insert"
    finally:
        state.close()


def test_persona_settings_are_private_and_only_change_wording(tmp_path):
    owner = Principal("owner", "owner", True)
    profiles = PersonaStore(tmp_path / "profiles")
    profile = Persona(humor=0.9, expressiveness=0.8)
    profiles.save(owner, profile)
    assert profiles.load(owner) == profile
    assert profile.local_style() == "playful"
    assert Persona(directness=0.95, verbosity=0.2).local_style() == "focused"
    reply = compose_with_persona(resolve_offline("hello"), profile,
                                  memory=DialogueMemory())
    assert reply.intent == "greeting"
    assert profiles.load(Principal("other", "owner", True)) == Persona()
    with pytest.raises(PermissionError):
        profiles.load(Principal("owner", "owner", True, "phone"))
    with pytest.raises(ValueError):
        profiles.save(owner, Persona(humor=float("nan")))
