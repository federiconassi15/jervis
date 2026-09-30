from ..audio.processing import rms
class AdaptiveVAD:
    def __init__(self):self.noise=.006
    def speech(self,frame):
        level=rms(frame);threshold=max(.008,self.noise*2.8);yes=level>=threshold
        if not yes:self.noise=self.noise*.97+level*.03
        return yes
