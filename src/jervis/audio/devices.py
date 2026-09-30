from ..models import AudioDevice
def list_devices():
    import sounddevice as sd
    hostapis=sd.query_hostapis();out=[]
    for i,item in enumerate(sd.query_devices()):
        api=int(item.get("hostapi",0));name=hostapis[api]["name"] if api<len(hostapis) else ""
        out.append(AudioDevice(i,str(item["name"]),int(item["max_input_channels"]),int(item["max_output_channels"]),float(item["default_samplerate"]),str(name)))
    return out
def default_devices():
    import sounddevice as sd
    try:return int(sd.default.device[0]),int(sd.default.device[1])
    except Exception:return None,None
