from __future__ import annotations

import hashlib
import urllib.request
from pathlib import Path
from typing import Callable

MODEL_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/"
    "speaker-recongition-models/wespeaker_en_voxceleb_resnet34.onnx"
)
MODEL_SHA256 = "5ef208a9da1453335308a6b6f4e6dfbd7e183a38b604de0a57664f45d257fe94"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_speaker_model(
    model_path: Path,
    progress: Callable[[str], None] | None = None,
) -> bool:
    model_path.parent.mkdir(parents=True, exist_ok=True)

    if model_path.exists() and sha256(model_path) == MODEL_SHA256:
        return True

    if progress:
        progress("Downloading local speaker-recognition model (~26.5 MB)")

    temp = model_path.with_suffix(".onnx.tmp")
    temp.unlink(missing_ok=True)
    try:
        request = urllib.request.Request(
            MODEL_URL,
            headers={"User-Agent": "Jervis/7.1"},
        )
        with urllib.request.urlopen(request, timeout=60) as response, temp.open("wb") as output:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)

        if sha256(temp) != MODEL_SHA256:
            raise RuntimeError("speaker model SHA-256 verification failed")

        temp.replace(model_path)
        return True
    except Exception:
        temp.unlink(missing_ok=True)
        return False
