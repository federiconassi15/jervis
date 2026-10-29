"""Voice turn state/cancellation and wake profile regression tests."""
import pytest

from jervis.speech.turns import Phase, TurnManager, SpeechChunkBuffer
from jervis.wake_studio import WakeProfile, WakeStudio


def test_stale_speaker_callback_cannot_reanimate_interrupted_turn():
    manager = TurnManager()
    first = manager.wake(session_id="verified-s1")
    assert manager.advance(first.id, Phase.WAKING, Phase.LISTENING)
    assert manager.advance(first.id, Phase.LISTENING, Phase.THINKING)
    assert manager.advance(first.id, Phase.THINKING, Phase.SPEAKING)
    second = manager.interrupt()
    assert first.cancelled.is_set()
    assert second.phase == Phase.LISTENING
    # Identity is NOT inherited automatically from an interrupted user.
    assert second.session_id is None
    assert not manager.advance(first.id, Phase.SPEAKING, Phase.LISTENING)
    assert not manager.finish(first.id)
    assert manager.advance(second.id, Phase.LISTENING, Phase.THINKING)
    assert manager.finish(second.id)
    assert manager.current() is None


def test_invalid_transitions_and_stop():
    manager = TurnManager()
    first = manager.wake()
    with pytest.raises(RuntimeError):
        manager.wake()
    with pytest.raises(ValueError):
        manager.advance(first.id, Phase.WAKING, Phase.SPEAKING)
    with pytest.raises(RuntimeError):
        manager.interrupt()
    manager.stop()
    assert first.cancelled.is_set()
    assert not manager.advance(first.id, Phase.WAKING, Phase.LISTENING)


def test_stream_buffer_yields_sentences_and_does_not_execute():
    stream = SpeechChunkBuffer(maximum_chars=128)
    assert stream.push("Hello") == []
    assert stream.push(" there. What's") == ["Hello there."]
    assert stream.push(" up?") == ["What's up?"]
    assert stream.flush() == ""
    assert stream.push("unfinished") == []
    stream.cancel()
    assert stream.flush() == ""
    with pytest.raises(ValueError):
        stream.push("a" * 129)


def test_wake_profile_validation_and_secure_roundtrip(tmp_path):
    studio = WakeStudio(tmp_path / "prefs" / "wake.json")
    assert studio.load()["default"].phrase == "jervis"
    config = {
        "default": WakeProfile("default", "jervis"),
        "quiet": WakeProfile("quiet", "hey jervis", threshold=1e-26),
    }
    studio.save(config)
    assert studio.load() == config
    with pytest.raises(ValueError):
        studio.save({"quiet": config["quiet"]})
    with pytest.raises(ValueError):
        studio.save({"default": WakeProfile("default", "hey; rm -rf /")})


def test_symlinked_profile_path_is_blocked(tmp_path):
    target = tmp_path / "outside.json"
    target.write_text("{}")
    link = tmp_path / "link.json"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("Symlink unavailable")
    with pytest.raises(PermissionError):
        WakeStudio(link)
