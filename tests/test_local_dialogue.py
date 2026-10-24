"""Jervis 8.1 dialogue renderer regression tests."""
import json
import random
from datetime import datetime
from types import SimpleNamespace

import pytest

from jervis.local_dialogue import DialogueMemory, DialogueStore, compose, reply_offline
from jervis.evolve import resolve_offline


def _intent(name):
    return SimpleNamespace(name=name, response="fallback", requires_confirmation=False)


@pytest.mark.parametrize("name", ["greeting", "help", "time", "status", "diagnostics"])
def test_repetition_creates_distinct_utterances(name):
    memory = DialogueMemory()
    rng = random.Random(23)
    clock = datetime(2026, 10, 24, 10, 30)
    replies = [compose(_intent(name), memory=memory, rng=rng, now=clock) for _ in range(8)]
    assert len({r.text for r in replies}) == len(replies)
    assert len({r.variant for r in replies}) == len(replies)
    assert len(memory.recent) == 8


def test_styles_are_distinct_and_have_no_unapproved_actions():
    memory = DialogueMemory()
    for style in ("focused", "playful", "balanced"):
        reply = compose(_intent("status"), memory=memory, style=style, rng=random.Random(2))
        assert "jervis status" in reply.text
    with pytest.raises(ValueError):
        compose(_intent("status"), style="malicious")


def test_personality_does_not_fabricate_live_status_or_diagnostics():
    for name, command in (("status", "jervis status"), ("diagnostics", "jervis doctor")):
        for seed in range(80):
            reply = compose(_intent(name), rng=random.Random(seed))
            assert command in reply.text
            assert "healthy" not in reply.text.lower()
            assert "fixed" not in reply.text.lower()


def test_time_uses_actual_provided_local_clock():
    clock = datetime(2026, 10, 24, 6, 7)
    for seed in range(45):
        reply = compose(_intent("time"), rng=random.Random(seed), now=clock)
        assert "06:07" in reply.text


def test_unrecognized_intent_is_not_inferred_or_executed():
    reply = compose(_intent("file_delete"))
    assert reply.text == "fallback"
    assert reply.variant == "canonical"
    assert resolve_offline("delete everything") is None


def test_memorizes_only_anonymous_variant_ids(tmp_path):
    cache = tmp_path / "dialogue.json"
    reply_offline(_intent("greeting"), cache=cache, rng=random.Random(1))
    data = json.loads(cache.read_text())
    assert data["version"] == 1
    assert set(data) == {"version", "recent", "frames", "last_intent", "streak"}
    assert "Hello" not in cache.read_text() and "Ready" not in cache.read_text()
    memory = DialogueStore(cache).load()
    assert memory.last_intent == "greeting"
    assert len(memory.recent) == 1


def test_repeated_cli_invocations_use_persisted_cooldown(tmp_path):
    cache = tmp_path / "dialogue.json"
    replies = [
        reply_offline(_intent("greeting"), cache=cache, rng=random.Random(7))
        for _ in range(10)
    ]
    assert len({reply.variant for reply in replies}) == 10


def test_focused_mode_stays_focused():
    memory = DialogueMemory()
    tones = [
        compose(_intent("greeting"), memory=memory, style="focused",
                rng=random.Random(1)).tone
        for _ in range(6)
    ]
    assert set(tones) == {"focused"}


def test_corrupt_or_untrusted_history_ignored(tmp_path):
    target = tmp_path / "history.json"
    target.write_text("not valid JSON")
    assert DialogueStore(target).load() == DialogueMemory()
    target.write_text("X" * 20000)
    assert DialogueStore(target).load() == DialogueMemory()
    target.write_text(json.dumps({
        "version": 1, "recent": [123, "a"],
        "frames": {"a": -1, "b": True},
        "last_intent": {}, "streak": -99,
    }))
    memory = DialogueStore(target).load()
    assert memory.recent == ["a"] and memory.frames == {} and memory.streak == 0


def test_symlink_history_never_followed(tmp_path):
    outside = tmp_path / "outside.json"
    outside.write_text("DO NOT CHANGE")
    symlink = tmp_path / "history.json"
    try:
        symlink.symlink_to(outside)
    except (NotImplementedError, OSError):
        pytest.skip("symlinks unavailable")
    store = DialogueStore(symlink)
    store.save(DialogueMemory())
    assert outside.read_text() == "DO NOT CHANGE"
    assert store.load() == DialogueMemory()


def test_memory_bounded_even_after_many_invocations():
    memory = DialogueMemory()
    rng = random.Random(7)
    for _ in range(150):
        compose(_intent("greeting"), memory=memory, rng=rng)
    assert len(memory.recent) <= 24
    assert len(memory.frames) < 64
    assert memory.streak <= 30


def test_fallback_returns_canonical_unchanged():
    intent = SimpleNamespace(
        name="unimplemented", response="The original response.",
        requires_confirmation=True,
    )
    reply = compose(intent)
    assert reply.text == intent.response
    assert reply.requires_confirmation is True
