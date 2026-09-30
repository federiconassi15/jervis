import queue,time
import numpy as np
from .audio import AndroidAudioSource,DesktopAudio
from .audio.processing import quality_score
from .brain import OpenClawBrain
from .config import load
from .identity import IdentityManager
from .paths import Paths
from .sessions import SessionManager
from .speaker import SpeakerRecognizer
from .speech import AdaptiveVAD,LazyWhisper,TTS,WakeDetector
from .state import State
class Runtime:
    def __init__(self):
        self.paths=Paths.resolve();self.paths.ensure();self.config=load(self.paths.config/"config.json")
        privacy=self.config["privacy"];ident=self.config["identity"];speech=self.config["speech"];brain=self.config["brain"]
        self.state=State(self.paths.data/"jervis.sqlite3",privacy["max_dialogue_rows"],privacy["max_event_rows"])
        self.sessions=SessionManager(self.state,ident["trusted_session_seconds"],ident["inactivity_seconds"])
        self.speaker=SpeakerRecognizer(self.state,ident,self.paths.data/"models/speaker.onnx")
        self.identity=IdentityManager(self.state,self.sessions,self.speaker,ident)
        self.stt=LazyWhisper(speech["stt_model"],speech["stt_device"],speech["compute_type"])
        self.tts=TTS(speech["tts_backend"],speech["edge_voice"])
        self.wake=WakeDetector(self.config["assistant"]["wake_word"],self.config["audio"]["sample_rate"])
        self.vad=AdaptiveVAD();self.brain=OpenClawBrain(brain["agent"],brain["timeout_seconds"],brain["thinking"]);self.running=True
    def source(self):
        audio=self.config["audio"];src=audio["source"]
        return AndroidAudioSource(src.get("android_serial"),audio["sample_rate"]) if src["kind"]=="android" else DesktopAudio(src.get("device"),audio.get("output_device"),audio["sample_rate"])
    def capture(self,audio,first=None):
        chunks=[] if first is None else [first];speaking=first is not None;silence=None;deadline=time.monotonic()+12
        while self.running and time.monotonic()<deadline:
            try:frame=audio.read()
            except queue.Empty:continue
            if self.vad.speech(frame):speaking=True;silence=None;chunks.append(frame)
            elif speaking:
                chunks.append(frame);silence=silence or time.monotonic()
                if time.monotonic()-silence>=0.75:break
        return np.concatenate(chunks) if chunks else np.zeros(0,dtype=np.float32)
    def speak(self,text,user_id=None):self.state.dialogue("jervis",text,user_id);self.tts.speak(text)
    def respond(self,text,user_id):
        user=self.state.user(user_id);self.state.dialogue(str(user["name"]) if user else user_id,text,user_id)
        reply=self.brain.ask(text,"jervis:"+user_id)
        if reply.ok:self.speak(reply.text,user_id)
        else:self.state.event("brain_error",reply.error);self.speak("My OpenClaw brain is unavailable, but I am still running locally.",user_id)
    def run(self):
        self.state.event("runtime_start","Jervis 7.1")
        with self.source() as audio:
            while self.running:
                try:frame=audio.read()
                except queue.Empty:self.stt.maybe_unload();continue
                if not self.wake.process(frame):continue
                self.state.event("wake","matched");self.speak(self.config["assistant"]["wake_acknowledgement"])
                command_audio=self.capture(audio)
                if command_audio.size<self.config["audio"]["sample_rate"]*0.25:continue
                command=self.stt.transcribe(command_audio,self.config["assistant"]["language"])
                if not command:self.speak("I didn't catch that.");continue
                identity=self.identity.identify(command_audio,self.config["audio"]["sample_rate"])
                if identity.needs_retry:
                    self.speak("One more time, boss?");retry=self.capture(audio);retry_text=self.stt.transcribe(retry,self.config["assistant"]["language"])
                    again=self.identity.identify(retry,self.config["audio"]["sample_rate"])
                    if again.authenticated and again.user_id:identity=again;command=retry_text or command
                if not identity.authenticated or not identity.user_id:
                    self.speak("I can't verify who's speaking. Authenticate in the Control Deck to continue.");self.state.event("identity_auth_required","voice confidence insufficient");continue
                q=quality_score(command_audio)
                if self.config["identity"]["continuous_learning"] and getattr(identity.match,"band",None) and identity.match.band.value=="strong" and q>=0.78:
                    self.speaker.learn(identity.user_id,command_audio,self.config["audio"]["sample_rate"],q)
                self.respond(command,identity.user_id);until=time.monotonic()+self.config["speech"]["follow_up_seconds"]
                while self.running and time.monotonic()<until:
                    try:follow=audio.read(timeout=0.5)
                    except (queue.Empty,TypeError):continue
                    if not self.vad.speech(follow):continue
                    follow_audio=self.capture(audio,follow);follow_text=self.stt.transcribe(follow_audio,self.config["assistant"]["language"])
                    if not follow_text:break
                    self.sessions.refresh();self.respond(follow_text,identity.user_id);until=time.monotonic()+self.config["speech"]["follow_up_seconds"]
