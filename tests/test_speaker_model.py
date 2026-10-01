from pathlib import Path

import jervis.speaker_model as model


def test_existing_verified_model_is_reused(monkeypatch, tmp_path):
    path = tmp_path / "speaker.onnx"
    path.write_bytes(b"model")
    monkeypatch.setattr(model, "sha256", lambda value: model.MODEL_SHA256)
    assert model.ensure_speaker_model(path)
