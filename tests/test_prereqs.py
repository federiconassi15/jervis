import jervis.prereqs as prereqs


def test_linux_tts_missing_is_installed_even_when_portaudio_exists(
    monkeypatch,
):
    monkeypatch.setattr(prereqs.platform, "system", lambda: "Linux")
    monkeypatch.setattr(prereqs, "portaudio_available", lambda: True)
    monkeypatch.setattr(prereqs, "_sudo", lambda: [])

    def which(name):
        if name == "apt-get":
            return "/usr/bin/apt-get"
        if name in {"espeak-ng", "espeak"}:
            return None
        return None

    monkeypatch.setattr(prereqs.shutil, "which", which)

    calls = []
    monkeypatch.setattr(
        prereqs,
        "_run",
        lambda command: calls.append(command),
    )

    checks = [False, True]
    monkeypatch.setattr(
        prereqs,
        "linux_tts_available",
        lambda: checks.pop(0),
    )

    prereqs.ensure_linux_audio(lambda prompt: True)

    assert calls == [
        ["apt-get", "-qq", "update"],
        ["apt-get", "-qq", "install", "-y", "espeak-ng"],
    ]


def test_linux_install_keeps_sudo_prompt_visible_but_packages_quiet(monkeypatch):
    monkeypatch.setattr(prereqs, "_sudo", lambda: ["sudo"])
    monkeypatch.setattr(
        prereqs.shutil,
        "which",
        lambda name: "/usr/bin/apt-get" if name == "apt-get" else None,
    )

    calls = []

    def fake_run(command, *, quiet=True):
        calls.append((command, quiet))

    monkeypatch.setattr(prereqs, "_run", fake_run)
    prereqs._linux_install(["libportaudio2", "espeak-ng"])

    assert calls == [
        (["sudo", "-v"], False),
        (["sudo", "-n", "apt-get", "-qq", "update"], True),
        (
            [
                "sudo",
                "-n",
                "apt-get",
                "-qq",
                "install",
                "-y",
                "libportaudio2",
                "espeak-ng",
            ],
            True,
        ),
    ]


def test_linux_audio_returns_when_everything_exists(monkeypatch):
    monkeypatch.setattr(prereqs.platform, "system", lambda: "Linux")
    monkeypatch.setattr(prereqs, "portaudio_available", lambda: True)
    monkeypatch.setattr(prereqs, "linux_tts_available", lambda: True)

    prereqs.ensure_linux_audio(
        lambda prompt: (_ for _ in ()).throw(
            AssertionError("prompt should not be called")
        )
    )
