from __future__ import annotations

import threading
from pathlib import Path

import numpy as np

from .models import ConfidenceBand, SpeakerMatch


class SherpaBackend:
    def __init__(self, model_path: Path | None) -> None:
        self.model_path = model_path
        self.extractor = None
        self._lock = threading.RLock()

    @property
    def available(self) -> bool:
        return bool(self.model_path and self.model_path.exists())

    def _load(self):
        with self._lock:
            if self.extractor is not None:
                return self.extractor
            if not self.available:
                raise RuntimeError("speaker model is not installed")

            import sherpa_onnx

            config = sherpa_onnx.SpeakerEmbeddingExtractorConfig(
                model=str(self.model_path)
            )
            if not config.validate():
                raise RuntimeError("invalid speaker model")
            self.extractor = sherpa_onnx.SpeakerEmbeddingExtractor(config)
            return self.extractor

    def prewarm(self) -> None:
        if not self.available:
            return

        def load() -> None:
            try:
                self._load()
            except Exception:
                pass

        threading.Thread(
            target=load,
            name="jervis-speaker-prewarm",
            daemon=True,
        ).start()

    def embed(self, samples, sample_rate: int) -> np.ndarray:
        extractor = self._load()
        stream = extractor.create_stream()
        stream.accept_waveform(
            sample_rate,
            np.asarray(samples, dtype=np.float32).reshape(-1),
        )
        stream.input_finished()
        vector = np.asarray(extractor.compute(stream), dtype=np.float32)
        if not vector.size:
            raise RuntimeError("speaker embedding failed")
        return vector / (np.linalg.norm(vector) + 1e-9)


class SpeakerRecognizer:
    def __init__(self, state, config: dict, model_path: Path | None = None) -> None:
        self.state = state
        self.config = config
        self.backend = SherpaBackend(model_path)
        self._matrix_cache: dict[str, np.ndarray] = {}

    def prewarm(self) -> None:
        self.backend.prewarm()

    def _matrix(self, user_id: str, embeddings: list[list[float]]) -> np.ndarray:
        cached = self._matrix_cache.get(user_id)
        if cached is not None and cached.shape[0] == len(embeddings):
            return cached

        matrix = np.asarray(embeddings, dtype=np.float32)
        if matrix.ndim != 2 or not matrix.size:
            return np.zeros((0, 0), dtype=np.float32)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        matrix = matrix / np.maximum(norms, 1e-9)
        self._matrix_cache[user_id] = matrix
        return matrix

    def match(self, samples, sample_rate: int, active_user: str | None) -> SpeakerMatch:
        if not self.backend.available:
            if active_user:
                return SpeakerMatch(
                    active_user,
                    0.0,
                    0.0,
                    ConfidenceBand.SESSION_ASSISTED,
                    "session-no-model",
                )
            return SpeakerMatch(None, 0.0, 0.0, ConfidenceBand.UNKNOWN, "no-model")

        try:
            query = self.backend.embed(samples, sample_rate)
        except Exception:
            if active_user:
                return SpeakerMatch(
                    active_user,
                    0.0,
                    0.0,
                    ConfidenceBand.SESSION_ASSISTED,
                    "session-backend-error",
                )
            return SpeakerMatch(
                None,
                0.0,
                0.0,
                ConfidenceBand.UNKNOWN,
                "backend-error",
            )

        scores: list[tuple[str, float]] = []
        for user_id, embeddings in self.state.embeddings().items():
            matrix = self._matrix(user_id, embeddings)
            if not matrix.size or matrix.shape[1] != query.size:
                continue
            similarities = matrix @ query
            top = np.sort(similarities)[-3:]
            if top.size:
                scores.append((user_id, float(np.mean(top))))

        scores.sort(key=lambda item: item[1], reverse=True)
        if not scores:
            return SpeakerMatch(
                None,
                0.0,
                0.0,
                ConfidenceBand.UNKNOWN,
                "embedding",
            )

        user_id, score = scores[0]
        second = scores[1][1] if len(scores) > 1 else -1.0
        margin = score - second
        config = self.config

        if (
            score >= float(config["strong_threshold"])
            and margin >= float(config["minimum_margin"])
        ):
            band = ConfidenceBand.STRONG
        elif active_user == user_id and score >= float(config["session_threshold"]):
            band = ConfidenceBand.SESSION_ASSISTED
        elif (
            score >= float(config["uncertain_threshold"])
            and margin >= float(config["minimum_margin"]) / 2
        ):
            band = ConfidenceBand.UNCERTAIN
        else:
            return SpeakerMatch(
                None,
                score,
                margin,
                ConfidenceBand.UNKNOWN,
                "embedding",
            )

        return SpeakerMatch(user_id, score, margin, band, "embedding")

    def learn(
        self,
        user_id: str,
        samples,
        sample_rate: int,
        quality: float,
    ) -> bool:
        if not self.backend.available or quality < 0.72:
            return False
        try:
            embedding = self.backend.embed(samples, sample_rate)
            self.state.add_embedding(
                user_id,
                embedding.tolist(),
                quality,
                int(self.config.get("max_embeddings_per_user", 12)),
            )
            self._matrix_cache.pop(user_id, None)
            return True
        except Exception:
            return False
