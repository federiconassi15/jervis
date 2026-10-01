from __future__ import annotations

import json

import numpy as np

from jervis.brain.openclaw import OpenClawBrain, _response_text
from jervis.fast import AdaptiveVAD, analyze_tuple, backend_name


def test_fast_audio_analysis_contract():
    samples = np.full(1600, 0.05, dtype=np.float32)
    level, clipping, score, label = analyze_tuple(samples)
    assert 0.049 <= level <= 0.051
    assert clipping == 0.0
    assert score > 0.7
    assert label == "good"
    assert backend_name()


def test_fast_vad_adapts():
    vad = AdaptiveVAD()
    quiet = np.zeros(480, dtype=np.float32)
    speech = np.full(480, 0.08, dtype=np.float32)
    assert not vad.speech(quiet)
    assert vad.speech(speech)


def test_openclaw_response_text_extracts_output_items():
    payload = {
        "output": [
            {
                "type": "message",
                "content": [
                    {"type": "output_text", "text": "Hello"},
                    {"type": "output_text", "text": "world"},
                ],
            }
        ]
    }
    assert _response_text(payload) == "Hello\nworld"


def test_openclaw_uses_gateway_http_for_low_thinking(monkeypatch):
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps(
                {
                    "output": [
                        {
                            "content": [
                                {"type": "output_text", "text": "fast reply"}
                            ]
                        }
                    ]
                }
            ).encode()

    def urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    brain = OpenClawBrain(
        "main",
        12,
        "low",
        gateway_http=True,
        gateway_url="http://127.0.0.1:18789",
    )
    reply = brain.ask("hello", "jervis:u1", thinking="low")
    assert reply.ok
    assert reply.text == "fast reply"
    assert brain.last_transport == "gateway-http"
    assert captured["url"].endswith("/v1/responses")
