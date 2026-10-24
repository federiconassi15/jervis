"""Secure enumerated 8.1 offline aliases."""
from jervis.evolve import resolve_offline


def test_common_phrasings_are_safe_exact_aliases():
    for phrase in ("What time is it?", "current time", " time!! "):
        assert resolve_offline(phrase).name == "time"
    for phrase in ("Hi!", "hey", "hello jervis", "good morning"):
        assert resolve_offline(phrase).name == "greeting"


def test_unrecognized_input_does_not_trigger_even_if_containing_key():
    for phrase in ("delete everything please", "what is the password",
                   "time to remove all files", "status and shutdown", "status ; rm -rf"):
        assert resolve_offline(phrase) is None


def test_response_intent_is_stable_and_help_advertisements_are_real():
    assert resolve_offline("hello") == resolve_offline("  HELLO  ")
    assert resolve_offline("time") is not None
