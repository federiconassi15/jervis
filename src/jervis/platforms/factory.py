import platform
def current_platform():
    system=platform.system()
    if system=="Linux":
        from .linux import LinuxPlatform
        return LinuxPlatform()
    if system=="Darwin":
        from .macos import MacOSPlatform
        return MacOSPlatform()
    if system=="Windows":
        from .windows import WindowsPlatform
        return WindowsPlatform()
    raise RuntimeError("unsupported operating system: "+system)
