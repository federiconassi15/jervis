from __future__ import annotations

import collections
import queue
import threading
import time

import numpy as np

from .audio import AndroidAudioSource, DesktopAudio
from .audio.processing import analyze, quality_score, rms
from .brain import OpenClawBrain
from .config import load
from .identity import IdentityManager
from .paths import Paths
from .presence import PresenceManager
from .proactive import ProactiveEngine
from .router import BrainRouter
from .sessions import SessionManager
from .speaker import SpeakerRecognizer
from .speech import AdaptiveVAD, LazyWhisper, TTS, WakeDetector
from .state import State


class Runtime:
    TRAINING_PHRASES = [
        "Jervis, systems are online and ready.",
        "The quick brown fox jumps over the lazy dog.",
        "My voice should be recognized locally.",
    ]

    def __init__(self) -> None:
        self.paths = Paths.resolve()
        self.paths.ensure()
        self.config = load(self.paths.config / "config.json")

        privacy = self.config["privacy"]
        identity_config = self.config["identity"]
        speech = self.config["speech"]
        brain = self.config["brain"]
        audio = self.config["audio"]

        self.state = State(
            self.paths.data / "jervis.sqlite3",
            privacy["max_dialogue_rows"],
            privacy["max_event_rows"],
        )
        self.sessions = SessionManager(
            self.state,
            identity_config["trusted_session_seconds"],
            identity_config["inactivity_seconds"],
        )
        self.speaker = SpeakerRecognizer(
            self.state,
            identity_config,
            self.paths.data / "models" / "speaker.onnx",
        )
        self.identity = IdentityManager(
            self.state,
            self.sessions,
            self.speaker,
            identity_config,
        )
        self.stt = LazyWhisper(
            speech["stt_model"],
            speech["stt_device"],
            speech["compute_type"],
            speech.get("stt_keep_warm_seconds", 900),
            speech.get("stt_beam_size", 1),
        )
        self.tts = TTS(
            speech["tts_backend"],
            speech["edge_voice"],
            output_device=audio.get("output_device"),
            volume=audio.get("jervis_volume", 1.0),
        )
        self.wake = WakeDetector(
            self.config["assistant"]["wake_word"],
            audio["sample_rate"],
        )
        self.vad = AdaptiveVAD()
        self.brain = OpenClawBrain(
            brain["agent"],
            brain["timeout_seconds"],
            brain["thinking"],
            gateway_http=brain.get("gateway_http", True),
            gateway_url=brain.get("gateway_url", "http://127.0.0.1:18789"),
            gateway_retry_seconds=brain.get("gateway_retry_seconds", 60),
        )
        self.router = BrainRouter(self.state, self.paths, self.brain, self.config)
        self.presence = PresenceManager(
            self.state,
            self.config["presence"]["timeout_seconds"],
        )
        self.proactive = ProactiveEngine(
            self.state,
            self.config["proactive"],
            lambda message: self.speak(message),
        )
        self.running = True
        self._audio = None
        self._pending_barge: np.ndarray | None = None
        self._last_activity: str | None = None
        self._volume_value = float(audio.get("jervis_volume", 1.0))
        self._volume_checked_at = 0.0
        self.activity("Idle — waiting for Jervis")
        self._prewarm()

    def _prewarm(self) -> None:
        if self.config["speech"].get("stt_prewarm", True):
            self.stt.prewarm()
        self.speaker.prewarm()
        threading.Thread(
            target=self.wake.prewarm,
            name="jervis-wake-prewarm",
            daemon=True,
        ).start()
        self.tts.prewarm(
            [
                self.config["assistant"]["wake_acknowledgement"],
                "I didn't catch that.",
                "One more time, boss?",
                "Who is this?",
                "Password incorrect.",
                "Understood.",
            ]
        )

    def activity(self, text: str) -> None:
        if text == self._last_activity:
            return
        self._last_activity = text
        self.state.set_kv("activity", text)

    def _volume(self) -> float:
        now = time.monotonic()
        if now - self._volume_checked_at >= 1.0:
            self._volume_value = float(
                self.state.get_kv(
                    "audio.jervis_volume",
                    self.config["audio"].get("jervis_volume", 1.0),
                )
            )
            self._volume_checked_at = now
        return self._volume_value

    def source(self):
        audio = self.config["audio"]
        source = audio["source"]
        if source["kind"] == "android":
            return AndroidAudioSource(
                source.get("android_serial"),
                audio["sample_rate"],
            )
        return DesktopAudio(
            source.get("device"),
            audio.get("output_device"),
            audio["sample_rate"],
        )

    def capture(
        self,
        audio,
        first=None,
        max_seconds: float | None = None,
    ) -> np.ndarray:
        chunks = [] if first is None else [first]
        speaking = first is not None
        silence = None
        endpoint = float(self.config["speech"].get("endpoint_silence_seconds", 0.45))
        limit = (
            float(max_seconds)
            if max_seconds is not None
            else float(self.config["speech"].get("max_command_seconds", 12.0))
        )
        deadline = time.monotonic() + limit

        while self.running and time.monotonic() < deadline:
            try:
                frame = audio.read(timeout=min(1.0, max(0.05, deadline - time.monotonic())))
            except queue.Empty:
                continue

            if self.vad.speech(frame):
                speaking = True
                silence = None
                chunks.append(frame)
            elif speaking:
                chunks.append(frame)
                silence = silence or time.monotonic()
                if time.monotonic() - silence >= endpoint:
                    break

        return (
            np.concatenate(chunks)
            if chunks
            else np.zeros(0, dtype=np.float32)
        )

    def speak(
        self,
        text: str,
        user_id: str | None = None,
        *,
        allow_barge: bool = False,
    ) -> None:
        self.tts.set_volume(self._volume())
        self.state.dialogue("jervis", text, user_id)
        self.activity("Speaking — " + text[:80])

        if not allow_barge or self._audio is None:
            try:
                self.tts.speak(text)
            except Exception as exc:
                self.state.event("tts_error", str(exc))
            if self._audio is not None and hasattr(self._audio, "flush"):
                try:
                    self._audio.flush()
                except Exception:
                    pass
            return

        errors: list[BaseException] = []

        def playback() -> None:
            try:
                self.tts.speak(text)
            except BaseException as exc:
                errors.append(exc)

        worker = threading.Thread(target=playback, name="jervis-tts", daemon=True)
        worker.start()

        started = time.monotonic()
        baseline: list[float] = []
        leak_floor: float | None = None
        pre: collections.deque[np.ndarray] = collections.deque(maxlen=8)
        hot = 0
        trigger_frame: np.ndarray | None = None

        while worker.is_alive():
            try:
                frame = self._audio.read(timeout=0.03)
            except queue.Empty:
                continue
            level = rms(frame)
            pre.append(frame)

            age = time.monotonic() - started
            if age < 0.25:
                baseline.append(level)
                continue

            if leak_floor is None:
                if baseline:
                    ordered = sorted(baseline)
                    leak_floor = ordered[len(ordered) // 2]
                else:
                    leak_floor = self.vad.noise
            trigger = max(0.025, leak_floor * 2.2, self.vad.noise * 4.0)
            hot = hot + 1 if level >= trigger else max(0, hot - 1)
            if hot >= 4:
                trigger_frame = frame
                self.tts.stop()
                break

        worker.join(timeout=2.0)

        if errors:
            self.state.event("tts_error", str(errors[0]))
            return

        if trigger_frame is not None:
            seed = list(pre)
            first = np.concatenate(seed) if seed else trigger_frame
            self._pending_barge = self.capture(
                self._audio,
                first=first,
                max_seconds=7.0,
            )
            self.state.event(
                "barge_in",
                "user=" + str(user_id or "unknown"),
            )
            return

        if hasattr(self._audio, "flush"):
            try:
                self._audio.flush()
            except Exception:
                pass

    def respond(self, text: str, user_id: str, log_user: bool = True) -> None:
        user = self.state.user(user_id)
        name = str(user["name"]) if user else user_id
        if log_user:
            self.state.dialogue(name, text, user_id)

        self.activity("Routing command")
        reply = self.router.ask(
            text,
            user_id,
            authenticated=True,
            context={"runtime": self, "user_id": user_id},
        )
        self.state.set_kv("brain.last_route", reply.route)
        if reply.ok:
            self.speak(reply.text, user_id, allow_barge=True)
        else:
            self.state.event("brain_error", reply.error)
            self.speak(
                "My OpenClaw brain is unavailable, but I am still running locally.",
                user_id,
            )

    def _consume_tui_grant(self) -> str | None:
        grant = self.state.pop_kv("auth.tui_grant")
        if not isinstance(grant, dict):
            return None
        try:
            issued = float(grant["issued_at"])
            user_id = str(grant["user_id"])
        except (KeyError, TypeError, ValueError):
            return None
        if time.time() - issued > 120:
            self.state.event("tui_auth_expired", "user=" + user_id)
            return None
        if self.state.user(user_id) is None:
            return None
        return user_id

    @staticmethod
    def _honorific_from_text(text: str) -> str | None:
        cleaned = text.lower().replace("'", "").replace(".", " ").replace(",", " ")
        words = set(cleaned.split())
        if "sir" in words:
            return "sir"
        if "maam" in words or "madam" in words:
            return "maam"
        return None

    @staticmethod
    def _yes(text: str) -> bool:
        lowered = text.strip().lower()
        return lowered in {"yes", "yeah", "yep", "correct", "right", "yes please"}

    def _onboard_if_needed(
        self,
        audio,
        user_id: str,
        seed_samples: list[np.ndarray] | None = None,
    ) -> None:
        user = self.state.user(user_id)
        if user is None:
            return

        existing_embeddings = self.state.embeddings().get(user_id, [])
        if not existing_embeddings:
            self.speak("Let's train your voice so I can recognize you more reliably.", user_id)
            accepted = 0
            recordings = list(seed_samples or [])
            for phrase in self.TRAINING_PHRASES:
                self.speak("Please say: " + phrase, user_id)
                sample = self.capture(audio, max_seconds=8)
                if sample.size:
                    recordings.append(sample)

            for recording in recordings:
                if self.speaker.learn(
                    user_id,
                    recording,
                    self.config["audio"]["sample_rate"],
                    quality_score(recording),
                ):
                    accepted += 1
            self.state.event(
                "voice_training",
                "user=" + user_id + " accepted=" + str(accepted),
            )

        user = self.state.user(user_id)
        if user is None or user["honorific"]:
            return

        for _ in range(3):
            self.speak(
                "Would you like me to address you as sir or ma'am?",
                user_id,
            )
            answer_audio = self.capture(audio, max_seconds=6)
            answer = self.stt.transcribe(
                answer_audio,
                self.config["assistant"]["language"],
            )
            honorific = self._honorific_from_text(answer)
            if honorific is None:
                self.speak("I didn't catch that. Please say sir or ma'am.", user_id)
                continue

            spoken = "Sir" if honorific == "sir" else "Ma'am"
            self.speak(spoken + ", correct?", user_id)
            confirm_audio = self.capture(audio, max_seconds=5)
            confirm = self.stt.transcribe(
                confirm_audio,
                self.config["assistant"]["language"],
            )
            if self._yes(confirm):
                self.state.upsert_user(
                    user_id,
                    str(user["name"]),
                    honorific,
                    str(user["role"]),
                )
                self.speak("Understood, " + spoken.lower() + ".", user_id)
                return
            self.speak("Understood. Let's try again.", user_id)

    def _authenticate_unknown(
        self,
        audio,
        command_audio: np.ndarray,
    ) -> str | None:
        granted = self._consume_tui_grant()
        if granted:
            self.sessions.create(granted, 1.0, "tui")
            self._onboard_if_needed(audio, granted, [command_audio])
            return granted

        self.activity("Unknown speaker — waiting for identity")
        self.speak("Who is this?")
        name_audio = self.capture(audio, max_seconds=7)
        name = self.stt.transcribe(
            name_audio,
            self.config["assistant"]["language"],
        ).strip()

        self.speak(
            "Enter the password in the authentication section in the TUI "
            "or say it out loud in 5, 4, 3, 2, 1."
        )
        password_audio = self.capture(audio, max_seconds=10)

        granted = self._consume_tui_grant()
        if granted:
            self.sessions.create(granted, 1.0, "tui")
            self._onboard_if_needed(audio, granted, [command_audio, name_audio])
            return granted

        spoken_password = self.stt.transcribe(
            password_audio,
            self.config["assistant"]["language"],
        )
        if not self.identity.verify_global_passphrase(spoken_password):
            self.state.event("voice_auth_failed", "unknown speaker")
            self.speak("Password incorrect.")
            return None

        user = self.state.user_by_name(name) if name else None
        if user is None:
            if not name:
                self.speak("I couldn't get your name. Use the authentication section in the TUI.")
                return None
            user_id = self.identity.create_user(name)
        else:
            user_id = str(user["id"])

        self.sessions.create(user_id, 1.0, "spoken-passphrase")
        self._onboard_if_needed(audio, user_id, [command_audio, name_audio])
        return user_id

    def run(self) -> None:
        self.state.event("runtime_start", "Jervis 7.3")

        with self.source() as audio:
            self._audio = audio
            while self.running:
                self.activity("Idle — waiting for Jervis")
                try:
                    frame = audio.read(timeout=1.0)
                except queue.Empty:
                    self.stt.maybe_unload()
                    if self.config["presence"]["enabled"]:
                        self.presence.sweep()
                    self.proactive.tick()
                    continue

                if not self.wake.process(frame):
                    continue

                self.state.event("wake", "matched")
                self.activity("Wake detected — listening for command")
                self.speak(self.config["assistant"]["wake_acknowledgement"])

                command_audio = self.capture(audio)
                if command_audio.size < self.config["audio"]["sample_rate"] * 0.25:
                    continue

                self.activity("Transcribing command")
                command = self.stt.transcribe(
                    command_audio,
                    self.config["assistant"]["language"],
                )
                if not command:
                    self.speak("I didn't catch that.")
                    continue

                identity = self.identity.identify(
                    command_audio,
                    self.config["audio"]["sample_rate"],
                )

                if identity.needs_retry:
                    self.speak("One more time, boss?")
                    retry = self.capture(audio)
                    retry_text = self.stt.transcribe(
                        retry,
                        self.config["assistant"]["language"],
                    )
                    again = self.identity.identify(
                        retry,
                        self.config["audio"]["sample_rate"],
                    )
                    if again.authenticated and again.user_id:
                        identity = again
                        command = retry_text or command
                        command_audio = retry

                logged_unknown = False
                if not identity.authenticated or not identity.user_id:
                    self.state.dialogue("unknown", command)
                    logged_unknown = True
                    user_id = self._authenticate_unknown(audio, command_audio)
                    if user_id is None:
                        self.activity("Authentication required — unknown speaker")
                        continue
                    identity.user_id = user_id
                    identity.authenticated = True

                user_id = identity.user_id
                if user_id is None:
                    continue

                if self.config["presence"]["enabled"]:
                    confidence = float(getattr(identity.match, "score", 1.0) or 1.0)
                    self.presence.seen(user_id, "voice", confidence)

                audio_quality = analyze(command_audio)
                self.state.set_kv(
                    "audio.last_quality",
                    {
                        "rms": audio_quality.rms,
                        "clipping": audio_quality.clipping,
                        "score": audio_quality.score,
                        "label": audio_quality.label,
                    },
                )
                if audio_quality.score < 0.5:
                    self.state.event(
                        "audio_quality",
                        audio_quality.label
                        + " score="
                        + format(audio_quality.score, ".2f"),
                    )

                quality = audio_quality.score
                if (
                    self.config["identity"]["continuous_learning"]
                    and getattr(identity.match, "band", None)
                    and identity.match.band.value == "strong"
                    and quality >= 0.78
                ):
                    self.speaker.learn(
                        user_id,
                        command_audio,
                        self.config["audio"]["sample_rate"],
                        quality,
                    )

                self.respond(command, user_id, log_user=not logged_unknown)

                while self._pending_barge is not None:
                    barged_audio = self._pending_barge
                    self._pending_barge = None
                    if barged_audio.size == 0:
                        break
                    self.activity("Barge-in — transcribing")
                    barged_text = self.stt.transcribe(
                        barged_audio,
                        self.config["assistant"]["language"],
                    )
                    if not barged_text:
                        break
                    self.sessions.refresh()
                    self.respond(barged_text, user_id)

                until = time.monotonic() + self.config["speech"]["follow_up_seconds"]

                while self.running and time.monotonic() < until:
                    self.activity("Follow-up window — listening")
                    try:
                        follow = audio.read(timeout=0.5)
                    except queue.Empty:
                        continue
                    if not self.vad.speech(follow):
                        continue

                    follow_audio = self.capture(audio, follow)
                    follow_text = self.stt.transcribe(
                        follow_audio,
                        self.config["assistant"]["language"],
                    )
                    if not follow_text:
                        break

                    self.sessions.refresh()
                    self.respond(follow_text, user_id)
                    until = time.monotonic() + self.config["speech"]["follow_up_seconds"]
