import numpy as np
def rms(samples):
    x=np.asarray(samples,dtype=np.float32);return 0.0 if x.size==0 else float(np.sqrt(np.mean(x*x,dtype=np.float64)))
def clipping_ratio(samples,threshold=.985):
    x=np.asarray(samples,dtype=np.float32);return 0.0 if x.size==0 else float(np.mean(np.abs(x)>=threshold))
def quality_score(samples):
    level=rms(samples);clip=clipping_ratio(samples)
    if level<.004:return .2
    if level>.5 or clip>.01:return .35
    return float(max(0,min(1,min(1,level/.06)*(1-min(.8,clip*20)))))
