import json

from jervis.openclaw_wizard import OpenClawWizardBridge


def test_wizard_json_decoder_accepts_direct_payload():
    payload = {
        "sessionId": "abc",
        "done": False,
        "status": "running",
        "step": {"id": "x", "type": "text", "sensitive": True},
    }
    assert OpenClawWizardBridge._decode_json(json.dumps(payload)) == payload


def test_wizard_json_decoder_unwraps_cli_envelope():
    payload = {
        "sessionId": "abc",
        "done": False,
        "status": "running",
        "step": {"id": "provider", "type": "select"},
    }
    wrapped = {"ok": True, "result": payload}
    assert OpenClawWizardBridge._decode_json(json.dumps(wrapped)) == payload


def test_wizard_json_decoder_tolerates_leading_cli_output():
    payload = {"done": True, "status": "done"}
    output = "OpenClaw gateway call\n" + json.dumps(payload)
    assert OpenClawWizardBridge._decode_json(output) == payload
