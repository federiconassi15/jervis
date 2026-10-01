import platform

from jervis.platforms.factory import current_platform
from jervis.platforms.linux import LinuxPlatform, _unit_quote
from jervis.platforms.macos import MacOSPlatform
from jervis.platforms.windows import WindowsPlatform, _ps_quote


def test_current_platform_matches_runner():
    adapter = current_platform()
    expected = {"Linux": "linux", "Windows": "windows", "Darwin": "macos"}[platform.system()]
    assert adapter.capabilities().name == expected


def test_all_platform_capabilities_are_complete():
    for adapter in (LinuxPlatform(), WindowsPlatform(), MacOSPlatform()):
        caps = adapter.capabilities()
        assert caps.name
        assert caps.desktop_startup
        assert caps.server_startup
        assert caps.audio_backend
        assert caps.supports_desktop
        assert caps.supports_server


def test_platform_quoting_helpers():
    assert _unit_quote('a"b') == '"a\\\"b"'
    assert _ps_quote("a'b") == "'a''b'"


def test_windows_task_argument_uses_cmd_double_quotes():
    wrapper = r"C:\\Program Files\\Jervis\\jervis-service.cmd"
    script = (
        "$wrapper=" + _ps_quote(wrapper) + ";"
        "$argument='/d /s /c ""' + $wrapper + '""';"
    )
    assert "\\\"" not in script
    assert "/d /s /c" in script
    assert "jervis-service.cmd" in script
