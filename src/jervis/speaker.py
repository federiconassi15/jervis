from pathlib import Path
import numpy as np
from .models import ConfidenceBand,SpeakerMatch
def cosine(a,b):
    av=np.asarray(a,dtype=np.float32);bv=np.asarray(b,dtype=np.float32)
    if av.size!=bv.size or not av.size:return -1.0
    av=av/(np.linalg.norm(av)+1e-9);bv=bv/(np.linalg.norm(bv)+1e-9)
    return float(np.dot(av,bv))
class SherpaBackend:
    def __init__(self,model_path:Path|None):self.model_path=model_path;self.extractor=None
    @property
    def available(self):return bool(self.model_path and self.model_path.exists())
    def _load(self):
        if self.extractor:return self.extractor
        if not self.available:raise RuntimeError("speaker model is not installed")
        import sherpa_onnx
        cfg=sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=str(self.model_path))
        if not cfg.validate():raise RuntimeError("invalid speaker model")
        self.extractor=sherpa_onnx.SpeakerEmbeddingExtractor(cfg);return self.extractor
    def embed(self,samples,sample_rate):
        ex=self._load();stream=ex.create_stream();stream.accept_waveform(sample_rate,np.asarray(samples,dtype=np.float32).reshape(-1));stream.input_finished()
        vector=np.asarray(ex.compute(stream),dtype=np.float32)
        if not vector.size:raise RuntimeError("speaker embedding failed")
        vector=vector/(np.linalg.norm(vector)+1e-9);return vector.tolist()
class SpeakerRecognizer:
    def __init__(self,state,config,model_path=None):self.state=state;self.config=config;self.backend=SherpaBackend(model_path)
    def match(self,samples,sample_rate,active_user):
        if not self.backend.available:
            return SpeakerMatch(active_user,0,0,ConfidenceBand.SESSION_ASSISTED,"session-no-model") if active_user else SpeakerMatch(None,0,0,ConfidenceBand.UNKNOWN,"no-model")
        try:query=self.backend.embed(samples,sample_rate)
        except Exception:
            return SpeakerMatch(active_user,0,0,ConfidenceBand.SESSION_ASSISTED,"session-backend-error") if active_user else SpeakerMatch(None,0,0,ConfidenceBand.UNKNOWN,"backend-error")
        scores=[]
        for uid,embs in self.state.embeddings().items():
            ranked=sorted((cosine(query,e) for e in embs),reverse=True)
            if ranked:scores.append((uid,sum(ranked[:3])/min(3,len(ranked))))
        scores.sort(key=lambda item:item[1],reverse=True)
        if not scores:return SpeakerMatch(None,0,0,ConfidenceBand.UNKNOWN,"embedding")
        uid,score=scores[0];second=scores[1][1] if len(scores)>1 else -1.0;margin=score-second;c=self.config
        if score>=float(c["strong_threshold"]) and margin>=float(c["minimum_margin"]):band=ConfidenceBand.STRONG
        elif active_user==uid and score>=float(c["session_threshold"]):band=ConfidenceBand.SESSION_ASSISTED
        elif score>=float(c["uncertain_threshold"]) and margin>=float(c["minimum_margin"])/2:band=ConfidenceBand.UNCERTAIN
        else:return SpeakerMatch(None,score,margin,ConfidenceBand.UNKNOWN,"embedding")
        return SpeakerMatch(uid,score,margin,band,"embedding")
    def learn(self,user_id,samples,sample_rate,quality):
        if not self.backend.available or quality<0.72:return False
        try:
            self.state.add_embedding(user_id,self.backend.embed(samples,sample_rate),quality,int(self.config.get("max_embeddings_per_user",12)))
            return True
        except Exception:return False
