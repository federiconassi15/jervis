from __future__ import annotations

import os
import platform
import random
import shutil
import subprocess
from pathlib import Path

import numpy as np
from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import (
    Button,
    Input,
    Label,
    LoadingIndicator,
    ProgressBar,
    Select,
    ContentSwitcher,
    Static,
    Switch,
)

from .audio.devices import default_devices, list_devices
from .install_engine import TOTAL_STEPS, run_install
from .install_plan import InstallOutcome, InstallPlan
from .openclaw_setup import configure_mode, find_openclaw
from .prereqs import ensure_linux_audio, find_adb

BANTER = [
    "Jervis, make me like Tony Stank.",
    "Teaching your computer manners.",
    "No arc reactor required.",
    "Deploying questionable amounts of intelligence.",
    "Please do not unplug reality.",
    "One moment, boss.",
    "Installing good decisions. Results may vary.",
    "Turning caffeine into automation.",
    "Giving your terminal a suspicious amount of personality.",
    "Arc reactor sold separately.",
]


class JervisInstaller(App[int]):
    TITLE = "Jervis Installer"
    SUB_TITLE = "7.1"

    CSS = """
    Screen {
        background: #020812;
        color: #d9f3ff;
        overflow: hidden;
    }

    #frame {
        width: 94%;
        max-width: 112;
        height: 100%;
        margin: 0 0;
        border: round #1db6ff;
        background: #04111f;
        padding: 0 2;
    }

    #hero {
        height: 4;
        content-align: center middle;
        color: #59d7ff;
        text-style: bold;
    }

    #tagline {
        height: 1;
        content-align: center middle;
        color: #6b91a8;
        text-style: italic;
    }

    #stepbar {
        height: 2;
        content-align: center middle;
        color: #4f788e;
        border-bottom: solid #0b3852;
    }

    #system-line {
        height: 1;
        content-align: center middle;
        color: #2d91b8;
    }

    #context {
        min-height: 3;
        border: round #0f4d70;
        background: #03131f;
        color: #8ccde8;
        padding: 0 2;
        margin: 1 0;
    }

    #nav-hint {
        width: 1fr;
        color: #527c91;
        content-align: left middle;
    }

    #audio-meter {
        height: 3;
        color: #75dfff;
        content-align: center middle;
    }

    #pages {
        height: 1fr;
        overflow: hidden;
    }

    .page {
        height: 100%;
        padding: 1 3;
    }

    .title {
        height: 3;
        color: #7de3ff;
        text-style: bold;
    }

    .hint {
        color: #779bad;
        margin-bottom: 1;
    }

    .card {
        border: round #124d70;
        background: #061725;
        padding: 1 2;
        margin: 1 0;
    }

    Select, Input {
        margin: 1 0;
        border: tall #176a96;
        background: #03101a;
    }

    Select:focus, Input:focus {
        border: tall #39c9ff;
    }

    Button {
        margin-right: 1;
        min-width: 14;
    }

    Button.-primary {
        background: #0879b3;
        color: white;
    }

    Button:focus {
        text-style: bold;
        background: #12aee8;
    }

    #nav {
        dock: bottom;
        height: 3;
        padding: 0 2;
        border-top: solid #0b3852;
        align: right middle;
        background: #04111f;
    }

    #pulse {
        color: #31c8ff;
        width: 4;
        content-align: center middle;
    }

    #progress-status {
        height: 3;
        color: #a9ebff;
        text-style: bold;
        content-align: center middle;
    }

    #progress-detail {
        height: 3;
        color: #7595a5;
        content-align: center top;
    }

    ProgressBar {
        margin: 2 4;
    }

    #done-mark {
        height: 5;
        content-align: center middle;
        color: #60ffb5;
        text-style: bold;
    }

    #error-mark {
        height: 4;
        content-align: center middle;
        color: #ff6f91;
        text-style: bold;
    }

    #review {
        border: round #176a96;
        background: #03101a;
        padding: 1 2;
        margin: 1 0;
        height: auto;
    }
    """

    BINDINGS = [
        ("up", "previous_control", "Previous control"),
        ("down", "next_control", "Next control"),
        ("left", "back", "Back"),
        ("right", "forward", "Next"),
    ]

    STEPS = ["Mode", "Brain", "Audio", "Identity", "Review", "Install"]

    def __init__(self) -> None:
        super().__init__()
        self.step = 0
        self.plan = InstallPlan()
        self.outcome: InstallOutcome | None = None
        self.core_installed = False
        self.tagline = random.choice(BANTER)
        self.pulse_frames = ["◐", "◓", "◑", "◒"]
        self.scan_frames = ["·", "•", "◆", "•"]
        self.hero_frames = [
            "J  E  R  V  I  S",
            "J · E · R · V · I · S",
            "J  E  R  V  I  S",
            "J › E › R › V › I › S",
        ]
        self.pulse_index = 0
        self.animation_tick = 0
        self.transition_ticks = 0
        self.progress_title = "Preparing…"
        self.progress_detail = ""
        self.inputs, self.outputs, self.androids = self._detect_audio()
        self.openclaw = find_openclaw()

    def _detect_audio(self):
        inputs = []
        outputs = []
        try:
            devices = list_devices()
            default_input, default_output = default_devices()
            for device in devices:
                if device.inputs > 0:
                    marker = " · default" if device.index == default_input else ""
                    inputs.append(
                        (
                            device.name + " · " + device.hostapi + marker,
                            "desktop:" + str(device.index),
                        )
                    )
                if device.outputs > 0:
                    marker = " · default" if device.index == default_output else ""
                    outputs.append(
                        (
                            device.name + " · " + device.hostapi + marker,
                            device.index,
                        )
                    )
        except Exception:
            pass

        androids = []
        adb = find_adb()
        if adb:
            try:
                proc = subprocess.run(
                    [str(adb), "devices"],
                    text=True,
                    capture_output=True,
                    timeout=5,
                    check=False,
                )
                androids = [
                    line.split("\t", 1)[0]
                    for line in proc.stdout.splitlines()
                    if line.endswith("\tdevice")
                ]
            except Exception:
                androids = []

        for serial in androids:
            inputs.append(("Android phone · " + serial, "android:" + serial))
        inputs.append(("Android phone · detect during setup", "android:auto"))
        return inputs, outputs, androids

    def compose(self) -> ComposeResult:
        with Container(id="frame"):
            with Horizontal():
                yield Static("◐", id="pulse")
                yield Static(
                    "J  E  R  V  I  S\nINTELLIGENT SYSTEMS INSTALLER",
                    id="hero",
                )
            yield Static("“" + self.tagline + "”", id="tagline")
            yield Static("", id="stepbar")
            yield Static("SYSTEM CHECK · READY", id="system-line")

            with ContentSwitcher(initial="page-mode", id="pages"):
                with VerticalScroll(classes="page", id="page-mode"):
                    yield Static("Where will Jervis live?", classes="title")
                    yield Static(
                        "Desktop uses the computer you work on every day. "
                        "Server is the always-on NUC/home-server style setup.",
                        classes="hint",
                    )
                    yield Select(
                        [
                            ("Desktop · everyday PC or Mac", "desktop"),
                            ("Server · always-on machine", "server"),
                        ],
                        value="desktop",
                        allow_blank=False,
                        id="mode",
                    )
                    yield Static(
                        self._platform_summary(),
                        classes="card",
                    )
                    yield Static("", id="context")

                with VerticalScroll(classes="page", id="page-brain"):
                    yield Static("Connect the OpenClaw brain", classes="title")
                    yield Static(
                        "Jervis handles OpenClaw installation quietly. "
                        "You only see OpenClaw directly when it genuinely needs your sign-in.",
                        classes="hint",
                    )
                    yield Static(
                        (
                            "● OpenClaw detected: " + str(self.openclaw)
                            if self.openclaw
                            else "○ OpenClaw is not installed yet"
                        ),
                        classes="card",
                        id="openclaw-status",
                    )
                    yield Select(
                        [
                            ("ChatGPT / Codex subscription · recommended", "codex"),
                            ("OpenAI API key", "api-key"),
                            ("Full OpenClaw setup / another provider", "full"),
                            ("Configure OpenClaw later", "later"),
                        ],
                        value="codex",
                        allow_blank=False,
                        id="openclaw-auth",
                    )
                    with Horizontal(classes="card"):
                        yield Label("Install OpenClaw automatically if missing")
                        yield Switch(value=True, id="openclaw-install")

                with VerticalScroll(classes="page", id="page-audio"):
                    yield Static("Choose how Jervis hears and speaks", classes="title")
                    yield Static(
                        "Use the detected devices below. Navigate with the arrow keys or click; type only in text fields.",
                        classes="hint",
                    )
                    yield Label("Microphone")
                    yield Select(
                        self.inputs,
                        prompt="Choose a microphone",
                        allow_blank=True,
                        id="microphone",
                    )
                    yield Label("Speakers / output")
                    yield Select(
                        self.outputs,
                        prompt="Choose an output",
                        allow_blank=True,
                        id="output",
                    )
                    with Horizontal():
                        yield Button("Test microphone", id="test-mic")
                        yield Button("Test speakers", id="test-output")
                    yield Static("MIC LEVEL  ·  not tested", id="audio-meter")
                    with Horizontal(classes="card"):
                        yield Label("Start Jervis automatically")
                        yield Switch(value=True, id="autostart")

                with VerticalScroll(classes="page", id="page-identity"):
                    yield Static("Create the owner profile", classes="title")
                    yield Static(
                        "This stays local. Jervis asks how to address people instead of guessing gender.",
                        classes="hint",
                    )
                    yield Input(placeholder="Your name", id="owner-name")
                    yield Select(
                        [("Sir", "sir"), ("Ma'am", "maam")],
                        value="sir",
                        allow_blank=False,
                        id="honorific",
                    )
                    yield Input(
                        placeholder="Jervis authentication passphrase",
                        password=True,
                        id="passphrase",
                    )
                    yield Input(
                        placeholder="Confirm passphrase",
                        password=True,
                        id="passphrase-confirm",
                    )
                    yield Static(
                        "The passphrase is never displayed in the review screen or normal logs.",
                        classes="hint",
                    )

                with VerticalScroll(classes="page", id="page-review"):
                    yield Static("Ready to build Jervis", classes="title")
                    yield Static("", id="review")
                    yield Static(
                        "Nothing is committed until the transactional install reaches its final checks.",
                        classes="hint",
                    )

                with VerticalScroll(classes="page", id="page-install"):
                    yield Static("Building Jervis", classes="title")
                    yield LoadingIndicator()
                    yield Static("Preparing…", id="progress-status")
                    yield Static("", id="progress-detail")
                    yield ProgressBar(total=TOTAL_STEPS, show_eta=False, id="progress")
                    yield Static("", id="error-mark")
                    yield Static("", id="done-mark")
                    yield Button("Continue to OpenClaw sign-in", id="auth-button", variant="primary")
                    yield Button("Finish", id="finish-button", variant="primary")

            with Horizontal(id="nav"):
                yield Static("↑↓ select/control   ← back   → next   mouse enabled", id="nav-hint")
                yield Button("Back", id="back")
                yield Button("Next", id="next", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#auth-button", Button).display = False
        self.query_one("#finish-button", Button).display = False
        self.set_interval(0.12, self._pulse_tick)
        self._render_stepbar()
        self._refresh_context()
        self.query_one("#mode", Select).focus()

    def _pulse_tick(self) -> None:
        self.animation_tick += 1
        self.pulse_index = (self.pulse_index + 1) % len(self.pulse_frames)
        self.query_one("#pulse", Static).update(self.pulse_frames[self.pulse_index])

        hero = self.hero_frames[(self.animation_tick // 2) % len(self.hero_frames)]
        self.query_one("#hero", Static).update(
            hero + "\nINTELLIGENT SYSTEMS INSTALLER"
        )

        scan = self.scan_frames[self.animation_tick % len(self.scan_frames)]
        if self.transition_ticks > 0:
            self.transition_ticks -= 1
            self.query_one("#system-line", Static).update(
                scan + " SYNCHRONIZING INTERFACE " + scan
            )
        elif self.step == 5 and not self.core_installed:
            self.query_one("#system-line", Static).update(
                scan + " BUILD SEQUENCE ACTIVE " + scan
            )
            self.query_one("#progress-status", Static).update(
                scan + "  " + self.progress_title
            )
        elif self.core_installed:
            self.query_one("#system-line", Static).update(
                "● CORE ONLINE · INSTALL VERIFIED"
            )
        else:
            self.query_one("#system-line", Static).update(
                scan + " SYSTEM CHECK · READY " + scan
            )

        if self.animation_tick % 80 == 0 and self.step < 5:
            self.tagline = random.choice(BANTER)
            self.query_one("#tagline", Static).update("“" + self.tagline + "”")

    def _platform_summary(self) -> str:
        return (
            platform.system()
            + " "
            + platform.release()
            + "  ·  "
            + platform.machine()
            + "  ·  bundled runtime"
        )

    def _refresh_context(self) -> None:
        if not self.is_mounted:
            return

        if self.step == 0:
            mode = str(self.query_one("#mode", Select).value)
            text = (
                "DESKTOP PROFILE  ·  interactive audio session · normal login startup"
                if mode == "desktop"
                else "SERVER PROFILE  ·  persistent startup · explicit always-on hardware"
            )
        elif self.step == 1:
            auth = str(self.query_one("#openclaw-auth", Select).value)
            labels = {
                "codex": "ChatGPT/Codex subscription · guided sign-in",
                "api-key": "OpenAI API key · provider credential setup",
                "full": "Full OpenClaw onboarding · alternate providers supported",
                "later": "Brain setup deferred · local Jervis remains usable",
            }
            text = "BRAIN LINK  ·  " + labels.get(auth, "select an authentication mode")
        elif self.step == 2:
            mic = self.query_one("#microphone", Select).value
            out = self.query_one("#output", Select).value
            mic_text = "waiting for microphone" if mic is Select.NULL else str(mic)
            out_text = "waiting for output" if out is Select.NULL else "output #" + str(out)
            text = "AUDIO ROUTE  ·  " + mic_text + "  →  " + out_text
        elif self.step == 3:
            name = self.query_one("#owner-name", Input).value.strip() or "owner not named yet"
            honorific = str(self.query_one("#honorific", Select).value)
            text = (
                "LOCAL IDENTITY  ·  "
                + name
                + " · address as "
                + ("ma'am" if honorific == "maam" else "sir")
                + " · passphrase encrypted locally"
            )
        elif self.step == 4:
            text = "FINAL CHECK  ·  review every choice before transactional activation"
        else:
            text = "INSTALL CORE  ·  staged changes · health checks · automatic rollback on failure"

        try:
            self.query_one("#context", Static).update(text)
        except Exception:
            pass

    def _render_stepbar(self) -> None:
        parts = []
        for index, name in enumerate(self.STEPS):
            if index < self.step:
                parts.append("✓ " + name)
            elif index == self.step:
                parts.append("● " + name)
            else:
                parts.append("○ " + name)
        self.query_one("#stepbar", Static).update("   ".join(parts))

    def _switch(self, step: int) -> None:
        self.step = max(0, min(step, len(self.STEPS) - 1))
        self.query_one("#pages", ContentSwitcher).current = [
            "page-mode",
            "page-brain",
            "page-audio",
            "page-identity",
            "page-review",
            "page-install",
        ][self.step]
        self.query_one("#back", Button).display = self.step not in {0, 5}
        self.query_one("#next", Button).display = self.step < 4
        self.transition_ticks = 7
        self._render_stepbar()
        self._refresh_context()
        focus_targets = {
            0: "#mode",
            1: "#openclaw-auth",
            2: "#microphone",
            3: "#owner-name",
        }
        target = focus_targets.get(self.step)
        if target:
            try:
                self.query_one(target).focus()
            except Exception:
                pass

    def _save_page(self) -> bool:
        try:
            if self.step == 0:
                self.plan.mode = str(self.query_one("#mode", Select).value)
                if self.plan.mode == "server":
                    self.query_one("#autostart", Switch).value = True
            elif self.step == 1:
                self.plan.openclaw_auth = str(
                    self.query_one("#openclaw-auth", Select).value
                )
                self.plan.install_openclaw = bool(
                    self.query_one("#openclaw-install", Switch).value
                )
            elif self.step == 2:
                mic_value = self.query_one("#microphone", Select).value
                output_value = self.query_one("#output", Select).value
                if mic_value is Select.NULL:
                    raise ValueError("Choose a microphone.")
                if output_value is Select.NULL:
                    raise ValueError("Choose an output device.")
                mic = str(mic_value)
                if mic.startswith("desktop:"):
                    self.plan.source_kind = "desktop"
                    self.plan.input_device = int(mic.split(":", 1)[1])
                    self.plan.android_serial = None
                else:
                    self.plan.source_kind = "android"
                    self.plan.input_device = None
                    serial = mic.split(":", 1)[1]
                    self.plan.android_serial = None if serial == "auto" else serial
                self.plan.output_device = int(output_value)
                self.plan.start_at_boot = (
                    True
                    if self.plan.mode == "server"
                    else bool(self.query_one("#autostart", Switch).value)
                )
            elif self.step == 3:
                name = self.query_one("#owner-name", Input).value.strip()
                first = self.query_one("#passphrase", Input).value
                second = self.query_one("#passphrase-confirm", Input).value
                if first != second:
                    raise ValueError("The passphrases do not match.")
                self.plan.owner_name = name
                self.plan.honorific = str(
                    self.query_one("#honorific", Select).value
                )
                self.plan.passphrase = first
                self.plan.validate()
            return True
        except Exception as exc:
            self.notify(str(exc), title="Check this step", severity="warning")
            return False

    def _update_review(self) -> None:
        microphone = (
            "Android phone"
            if self.plan.source_kind == "android"
            else "Computer microphone #" + str(self.plan.input_device)
        )
        brain = {
            "codex": "ChatGPT / Codex subscription",
            "api-key": "OpenAI API key",
            "full": "Full OpenClaw setup",
            "later": "Configure later",
        }[self.plan.openclaw_auth]
        lines = [
            "[b]Mode[/b]           " + self.plan.mode.title(),
            "[b]Brain[/b]          " + brain,
            "[b]Microphone[/b]     " + microphone,
            "[b]Output[/b]         Device #" + str(self.plan.output_device),
            "[b]Start at boot[/b]  " + ("Yes" if self.plan.start_at_boot else "No"),
            "[b]Owner[/b]          " + self.plan.owner_name,
            "[b]Address as[/b]     " + ("Ma'am" if self.plan.honorific == "maam" else "Sir"),
            "[b]Passphrase[/b]     ••••••••••••",
        ]
        self.query_one("#review", Static).update("\n".join(lines))

    @on(Select.Changed)
    def selection_changed(self, event: Select.Changed) -> None:
        del event
        self._refresh_context()

    @on(Switch.Changed)
    def switch_changed(self, event: Switch.Changed) -> None:
        del event
        self._refresh_context()

    @on(Input.Changed)
    def input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "owner-name":
            self._refresh_context()

    @on(Button.Pressed, "#next")
    def next_page(self) -> None:
        if self.step == 4:
            self.start_install()
            return
        if not self._save_page():
            return
        if self.step == 3:
            self._update_review()
        self._switch(self.step + 1)

    @on(Button.Pressed, "#back")
    def back_page(self) -> None:
        self._switch(self.step - 1)

    @on(Button.Pressed, "#test-output")
    def test_output_pressed(self) -> None:
        self.test_output()

    @work(thread=True, exclusive=True, group="audio-test")
    def test_output(self) -> None:
        value = self.query_one("#output", Select).value
        if value is Select.NULL:
            self.call_from_thread(
                self.notify,
                "Choose an output device first.",
                title="Audio",
                severity="warning",
            )
            return
        try:
            import sounddevice as sd

            rate = 16000
            timeline = np.arange(int(rate * 0.25), dtype=np.float32) / rate
            tone = (0.12 * np.sin(2 * np.pi * 440 * timeline)).astype(np.float32)
            sd.play(tone, samplerate=rate, device=int(value))
            sd.wait()
            self.call_from_thread(self.notify, "Speaker test complete.", title="Audio")
        except Exception as exc:
            self.call_from_thread(
                self.notify,
                str(exc),
                title="Speaker test failed",
                severity="error",
            )

    @on(Button.Pressed, "#test-mic")
    def test_mic_pressed(self) -> None:
        self.test_microphone()

    @work(thread=True, exclusive=True, group="audio-test")
    def test_microphone(self) -> None:
        value = self.query_one("#microphone", Select).value
        if value is Select.NULL or not str(value).startswith("desktop:"):
            self.call_from_thread(
                self.notify,
                "Select a computer microphone to run this quick test.",
                title="Audio",
                severity="warning",
            )
            return
        try:
            import sounddevice as sd

            rate = 16000
            device = int(str(value).split(":", 1)[1])
            recording = sd.rec(
                int(rate * 0.8),
                samplerate=rate,
                channels=1,
                dtype="float32",
                device=device,
            )
            sd.wait()
            level = float(np.sqrt(np.mean(np.square(recording), dtype=np.float64)))
            blocks = min(16, max(0, int(level / 0.004)))
            meter = "█" * blocks + "░" * (16 - blocks)
            label = (
                "GOOD"
                if 0.008 <= level <= 0.35
                else ("QUIET" if level < 0.008 else "LOUD")
            )
            self.call_from_thread(
                self._update_mic_meter,
                meter,
                level,
                label,
            )
            self.call_from_thread(
                self.notify,
                "Microphone test: " + label.lower(),
                title="Audio",
                severity="information" if label == "GOOD" else "warning",
            )
        except Exception as exc:
            self.call_from_thread(
                self.notify,
                str(exc),
                title="Microphone test failed",
                severity="error",
            )

    def _update_mic_meter(self, meter: str, level: float, label: str) -> None:
        self.query_one("#audio-meter", Static).update(
            "MIC LEVEL  " + meter + "  " + label + "  ·  RMS " + format(level, ".4f")
        )

    @on(Button.Pressed, "#auth-button")
    def auth_button_pressed(self) -> None:
        if not self.outcome or not self.outcome.openclaw_cli:
            self._show_done()
            return
        try:
            self.notify(
                "Jervis is temporarily handing the terminal to OpenClaw for the sign-in step.",
                title="OpenClaw",
            )
            with self.suspend():
                configure_mode(
                    Path(self.outcome.openclaw_cli),
                    self.plan.mode,
                    self.plan.openclaw_auth,
                )
        except Exception as exc:
            self.query_one("#error-mark", Static).update(
                "OpenClaw sign-in did not finish\n" + str(exc)
            )
            self.query_one("#progress-status", Static).update(
                "Jervis is installed. OpenClaw sign-in can be retried later."
            )
            self.query_one("#progress-detail", Static).update(
                "Retry here, or finish now and configure OpenClaw from its CLI later."
            )
            self.query_one("#finish-button", Button).display = True
            return
        self._show_done()

    @on(Button.Pressed, "#finish-button")
    def finish_pressed(self) -> None:
        self.exit(0)

    def action_back(self) -> None:
        if 0 < self.step < 5:
            self._switch(self.step - 1)

    def action_forward(self) -> None:
        if self.step < 5:
            self.next_page()

    def action_quit(self) -> None:
        self.exit(0 if self.core_installed else 130)

    def action_previous_control(self) -> None:
        self.screen.focus_previous()

    def action_next_control(self) -> None:
        self.screen.focus_next()

    def start_install(self) -> None:
        try:
            self.plan.validate()
        except Exception as exc:
            self.notify(str(exc), title="Review", severity="warning")
            return
        self._switch(5)
        self.query_one("#progress", ProgressBar).update(progress=0)
        self.progress_title = "Initializing transactional installer"
        self.progress_detail = "Preparing staged changes and rollback checkpoints."
        self.query_one("#progress-detail", Static).update(self.progress_detail)
        self.perform_install()

    @work(thread=True, exclusive=True, group="install")
    def perform_install(self) -> None:
        try:
            launcher = self._launcher_from_environment()
            outcome = run_install(
                self.plan,
                launcher,
                self._progress_from_worker,
            )
        except Exception as exc:
            self.call_from_thread(self._install_failed, str(exc))
            return
        self.call_from_thread(self._install_complete, outcome)

    def _launcher_from_environment(self) -> Path:
        override = os.environ.get("JERVIS_LAUNCHER_PATH")
        if override:
            return Path(override)
        found = shutil.which("jervis")
        if found:
            return Path(found)
        raise RuntimeError("Jervis launcher could not be located.")

    def _progress_from_worker(
        self,
        step: int,
        total: int,
        title: str,
        detail: str,
    ) -> None:
        self.call_from_thread(self._update_progress, step, total, title, detail)

    def _update_progress(
        self,
        step: int,
        total: int,
        title: str,
        detail: str,
    ) -> None:
        self.progress_title = title
        self.progress_detail = detail
        self.query_one("#progress", ProgressBar).update(total=total, progress=step)
        self.query_one("#progress-status", Static).update(
            self.scan_frames[self.animation_tick % len(self.scan_frames)]
            + "  "
            + title
        )
        self.query_one("#progress-detail", Static).update(
            "["
            + str(step)
            + "/"
            + str(total)
            + "]  "
            + detail
        )

    def _install_failed(self, message: str) -> None:
        self.query_one(LoadingIndicator).display = False
        self.query_one("#error-mark", Static).update(
            "Installation stopped safely\n" + message
        )
        self.query_one("#progress-status", Static).update("Nothing half-installed was left active.")
        self.query_one("#progress-detail", Static).update(
            "Fix the issue, then run the installer again."
        )
        self.query_one("#back", Button).display = True

    def _install_complete(self, outcome: InstallOutcome) -> None:
        self.outcome = outcome
        self.core_installed = True
        self.query_one(LoadingIndicator).display = False
        self.query_one("#progress", ProgressBar).update(
            total=TOTAL_STEPS,
            progress=TOTAL_STEPS,
        )
        if outcome.warnings:
            self.query_one("#progress-detail", Static).update(
                "\n".join("• " + item for item in outcome.warnings)
            )
        needs_auth = bool(
            outcome.openclaw_cli
            and self.plan.openclaw_auth != "later"
        )
        if needs_auth:
            self.query_one("#progress-status", Static).update(
                "Jervis is installed. One sign-in remains."
            )
            self.query_one("#auth-button", Button).display = True
        else:
            self._show_done()

    def _show_done(self) -> None:
        self.query_one("#auth-button", Button).display = False
        self.query_one("#progress-status", Static).update("Installation complete")
        self.query_one("#done-mark", Static).update(
            "✓ JERVIS 7.1 IS ONLINE\nRun  jervis doctor  any time for a health check."
        )
        self.query_one("#finish-button", Button).display = True


def _prepare_host_before_tui() -> None:
    # Fresh-machine setup is intentionally non-interactive before Textual starts.
    # Linux prerequisites are provisioned automatically so the installer never
    # falls back to a plain stdin [Y/n] prompt.
    ensure_linux_audio(lambda _message: True)


def install() -> int:
    """Prepare host prerequisites, launch the TUI, and return a process exit code."""
    try:
        _prepare_host_before_tui()
        result = JervisInstaller().run(mouse=True)
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print("Jervis installer could not start: " + str(exc))
        return 1
    return 130 if result is None else int(result)


def main() -> None:
    raise SystemExit(install())


if __name__ == "__main__":
    main()
