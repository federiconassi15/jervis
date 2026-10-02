from __future__ import annotations

import os
import platform
import random
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import numpy as np
from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.css.query import NoMatches
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
from .openclaw_providers import provider, select_options
from .openclaw_setup import configure_interactive_authorization, find_openclaw
from .prereqs import ensure_linux_audio, find_adb
from .version import __version__

BANTER = [
    "Local. Fast. Yours.",
    "Preparing your assistant.",
    "OpenClaw connected when you need it.",
    "Built for the machine in front of you.",
    "Private state. Explicit permissions.",
    "Voice, memory, agents — one system.",
]


_CUE_PATTERNS: dict[str, tuple[tuple[int, int], ...]] = {
    "boot": ((760, 55), (980, 70)),
    "install": ((880, 45), (1120, 70)),
    "complete": ((1040, 65), (1320, 90)),
    "attention": ((720, 75), (720, 75), (480, 135)),
}


def _terminal_cue(kind: str) -> None:
    """Emit a short terminal-style cue without adding an audio dependency."""
    disabled = os.environ.get("JERVIS_TERMINAL_CUES", "1").strip().lower()
    if disabled in {"0", "false", "no", "off"}:
        return

    force = os.environ.get("JERVIS_FORCE_TERMINAL_CUES", "").strip().lower()
    if force not in {"1", "true", "yes", "on"}:
        if not getattr(sys.stdout, "isatty", lambda: False)():
            return

    pattern = _CUE_PATTERNS.get(kind, _CUE_PATTERNS["attention"])

    def play() -> None:
        if platform.system() == "Windows":
            try:
                import winsound
                for frequency, duration_ms in pattern:
                    winsound.Beep(frequency, duration_ms)
                    time.sleep(0.025)
                return
            except Exception:
                pass

        for _frequency, duration_ms in pattern:
            try:
                sys.stdout.write("\a")
                sys.stdout.flush()
            except Exception:
                return
            time.sleep(max(0.04, duration_ms / 1000.0))

    threading.Thread(
        target=play,
        name="jervis-terminal-cue",
        daemon=True,
    ).start()


class JervisInstaller(App[int]):
    TITLE = "Jervis Installer"
    SUB_TITLE = __version__

    CSS = """
    Screen {
        background: #02070d;
        color: #d8eef8;
        overflow: hidden;
    }

    #frame {
        width: 92%;
        max-width: 108;
        height: 100%;
        margin: 0 0;
        background: #050d14;
        padding: 0 3;
    }

    #topline {
        height: 1;
        color: #2aa8d8;
        content-align: center middle;
    }

    #hero {
        height: 3;
        content-align: center middle;
        color: #87e4ff;
        text-style: bold;
    }

    #tagline {
        height: 1;
        content-align: center middle;
        color: #66889a;
    }

    #stepbar {
        height: 2;
        content-align: center middle;
        color: #537487;
        border-bottom: solid #102a38;
    }

    #system-line {
        height: 1;
        content-align: center middle;
        color: #318db0;
        margin-top: 1;
    }

    #context {
        min-height: 2;
        background: #07151f;
        color: #a5d9eb;
        padding: 0 2;
        margin: 1 0;
    }

    #pages {
        height: 1fr;
        overflow: hidden;
    }

    .page {
        height: 100%;
        padding: 1 2;
    }

    .title {
        height: 2;
        color: #d8f6ff;
        text-style: bold;
    }

    .hint {
        color: #6f8e9e;
        margin-bottom: 1;
    }

    .card {
        background: #07151f;
        padding: 1 2;
        margin: 1 0;
    }

    Select, Input {
        margin: 1 0;
        background: #06111a;
        border: tall #173c50;
    }

    Select:focus, Input:focus {
        border: tall #49cfff;
        background: #071824;
    }

    Switch {
        margin-left: 2;
    }

    Button {
        min-width: 14;
        margin-right: 1;
        background: #0b1b26;
        color: #cbefff;
        border: tall #173c50;
    }

    Button:hover, Button:focus {
        background: #0d2d3f;
        border: tall #49cfff;
        text-style: bold;
    }

    Button.-primary {
        background: #0c658b;
        color: white;
        border: tall #2abde9;
    }

    #nav {
        dock: bottom;
        height: 2;
        padding: 0 1;
        border-top: solid #102a38;
        align: right middle;
        background: #050d14;
    }

    #nav Button {
        height: 1;
        border: none;
        padding: 0 1;
    }

    #nav-hint {
        width: 1fr;
        color: #58788a;
        content-align: left middle;
    }

    #pulse {
        width: 3;
        color: #52d3ff;
        content-align: center middle;
    }

    #audio-meter {
        height: 2;
        color: #75dfff;
        content-align: center middle;
        background: #06131d;
        margin: 1 0;
    }

    #progress-status {
        height: 2;
        color: #c3efff;
        text-style: bold;
        content-align: center middle;
    }

    #progress-detail {
        height: 3;
        color: #6f93a5;
        content-align: center top;
    }

    ProgressBar {
        margin: 1 4;
    }

    #done-mark {
        height: 4;
        content-align: center middle;
        color: #7df0bd;
        text-style: bold;
    }

    #error-mark {
        height: 4;
        content-align: center middle;
        color: #ff8ca5;
        text-style: bold;
    }

    #review {
        background: #07151f;
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
            "╭──────────── J  E  R  V  I  S ────────────╮",
            "╭──────────── J · E · R · V · I · S ────────────╮",
            "╭──────────── J  E  R  V  I  S ────────────╮",
            "╭──────────── J  E  R  V  I  S ────────────╮",
        ]
        self.pulse_index = 0
        self.animation_tick = 0
        self.transition_ticks = 0
        self.progress_title = "Preparing…"
        self.progress_detail = ""
        self.inputs, self.outputs, self.androids = self._detect_audio()
        self.select_values = {
            "mode": ["desktop", "server"],
            "openclaw-auth": [value for _label, value in select_options()],
            "openclaw-gateway-bind": ["loopback", "auto", "lan", "tailnet"],
            "openclaw-gateway-auth": ["generated-token", "token", "password"],
            "openclaw-daemon-runtime": ["node", "bun"],
            "openclaw-node-manager": ["npm", "pnpm", "bun"],
            "openclaw-custom-compat": ["openai", "openai-responses", "anthropic"],
            "microphone": [value for _label, value in self.inputs],
            "output": [value for _label, value in self.outputs],
            "honorific": ["sir", "maam"],
        }
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
            yield Static(
                "┌─ SYSTEM BOOTSTRAP // JERVIS " + __version__ + " ─┐",
                id="topline",
            )
            with Horizontal():
                yield Static("◐", id="pulse")
                yield Static(
                    "╭──────────── J  E  R  V  I  S ────────────╮\n"
                    "│        INSTALLATION CONTROL DECK         │\n"
                    "╰──────────────────────────────────────────╯",
                    id="hero",
                )
            yield Static("‹ " + self.tagline + " ›", id="tagline")
            yield Static("", id="stepbar")
            yield Static("SYSTEM CHECK · READY", id="system-line")
            yield Static("", id="context")

            with ContentSwitcher(initial="page-mode", id="pages"):
                with VerticalScroll(classes="page", id="page-mode"):
                    yield Static("┌─ 01 // DEPLOYMENT MODE ───────────────────┐", classes="title")
                    yield Static(
                        "Desktop follows your normal login and audio session. "
                        "Server is tuned for an always-on machine.",
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

                with VerticalScroll(classes="page", id="page-brain"):
                    yield Static("┌─ 02 // OPENCLAW BRAIN ─────────────────────┐", classes="title")
                    yield Static(
                        "Jervis owns the setup flow. OpenClaw runs behind this screen.",
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
                    yield Label("AI provider / authentication")
                    yield Select(
                        select_options(),
                        value="openai",
                        allow_blank=False,
                        id="openclaw-auth",
                    )
                    yield Input(
                        placeholder="Provider API key / token",
                        password=True,
                        id="openclaw-provider-key",
                    )
                    yield Input(
                        value="main",
                        placeholder="OpenClaw agent name",
                        id="openclaw-agent-name",
                    )

                    yield Static(
                        "UNIVERSAL OPENCLAW PROVIDER",
                        classes="hint",
                        id="openclaw-universal-title",
                    )
                    yield Input(
                        placeholder="OpenClaw auth-choice id · e.g. future-provider-api-key",
                        id="openclaw-universal-auth-choice",
                    )
                    yield Input(
                        placeholder="Credential env var · e.g. FUTURE_PROVIDER_API_KEY",
                        id="openclaw-universal-env",
                    )
                    yield Input(
                        placeholder="Official plugin package · optional",
                        id="openclaw-universal-plugin",
                    )

                    yield Static("CUSTOM / LOCAL PROVIDER", classes="hint", id="openclaw-custom-title")
                    yield Input(
                        placeholder="Base URL · e.g. https://llm.example.com/v1",
                        id="openclaw-custom-base-url",
                    )
                    yield Input(
                        placeholder="Model ID · e.g. foo-large",
                        id="openclaw-custom-model-id",
                    )
                    yield Input(
                        placeholder="Provider ID · optional",
                        id="openclaw-custom-provider-id",
                    )
                    yield Select(
                        [
                            ("OpenAI chat/completions compatible", "openai"),
                            ("OpenAI Responses compatible", "openai-responses"),
                            ("Anthropic compatible", "anthropic"),
                        ],
                        value="openai",
                        allow_blank=False,
                        id="openclaw-custom-compat",
                    )
                    with Horizontal(classes="card", id="openclaw-custom-image-row"):
                        yield Label("Model accepts image input")
                        yield Switch(value=False, id="openclaw-custom-image")

                    yield Static("GATEWAY", classes="hint")
                    yield Select(
                        [
                            ("Loopback only · safest default", "loopback"),
                            ("Auto · container aware", "auto"),
                            ("LAN · private network exposure", "lan"),
                            ("Tailnet · Tailscale IP", "tailnet"),
                        ],
                        value="loopback",
                        allow_blank=False,
                        id="openclaw-gateway-bind",
                    )
                    yield Select(
                        [
                            ("Generate a Gateway token automatically", "generated-token"),
                            ("Use my Gateway token", "token"),
                            ("Use a Gateway password", "password"),
                        ],
                        value="generated-token",
                        allow_blank=False,
                        id="openclaw-gateway-auth",
                    )
                    yield Input(
                        placeholder="Gateway token / password",
                        password=True,
                        id="openclaw-gateway-secret",
                    )

                    yield Static("RUNTIME + OPTIONAL SETUP", classes="hint")
                    yield Select(
                        [("Node · recommended", "node"), ("Bun", "bun")],
                        value="node",
                        allow_blank=False,
                        id="openclaw-daemon-runtime",
                    )
                    yield Select(
                        [("npm", "npm"), ("pnpm", "pnpm"), ("bun", "bun")],
                        value="npm",
                        allow_blank=False,
                        id="openclaw-node-manager",
                    )
                    with Horizontal(classes="card"):
                        yield Label("Install OpenClaw automatically if missing")
                        yield Switch(value=True, id="openclaw-install")
                    with Horizontal(classes="card"):
                        yield Label("Install OpenClaw Gateway daemon")
                        yield Switch(value=True, id="openclaw-daemon")
                    with Horizontal(classes="card"):
                        yield Label("Set up skills")
                        yield Switch(value=True, id="openclaw-skills")
                    with Horizontal(classes="card"):
                        yield Label("Set up hooks")
                        yield Switch(value=True, id="openclaw-hooks")
                    with Horizontal(classes="card"):
                        yield Label("Set up channels")
                        yield Switch(value=False, id="openclaw-channels")
                    with Horizontal(classes="card"):
                        yield Label("Set up web search")
                        yield Switch(value=True, id="openclaw-search")

                    with Horizontal(classes="card", id="openclaw-plugin-consent-row"):
                        yield Label(
                            "Allow required official provider plugin capabilities"
                        )
                        yield Switch(value=False, id="openclaw-plugin-capabilities")
                    with Horizontal(classes="card"):
                        yield Label(
                            "I understand OpenClaw agents can use tools and system access"
                        )
                        yield Switch(value=False, id="openclaw-risk")

                with VerticalScroll(classes="page", id="page-audio"):
                    yield Static("┌─ 03 // AUDIO MATRIX ───────────────────────┐", classes="title")
                    yield Static(
                        "Pick the microphone and output Jervis should own.",
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
                    yield Static("┌─ 04 // IDENTITY CORE ──────────────────────┐", classes="title")
                    yield Static(
                        "Your local owner profile controls identity, permissions, and authentication.",
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
                    yield Static("┌─ 05 // FINAL REVIEW ───────────────────────┐", classes="title")
                    yield Static("", id="review")
                    yield Static(
                        "Nothing is committed until the transactional install reaches its final checks.",
                        classes="hint",
                    )

                with VerticalScroll(classes="page", id="page-install"):
                    yield Static("┌─ 06 // INSTALLATION SEQUENCE ──────────────┐", classes="title")
                    yield LoadingIndicator()
                    yield Static("Preparing…", id="progress-status")
                    yield Static("", id="progress-detail")
                    yield ProgressBar(total=TOTAL_STEPS, show_eta=False, id="progress")
                    yield Static("", id="error-mark")
                    yield Static("", id="done-mark")
                    yield Button("Continue to OpenClaw sign-in", id="auth-button", variant="primary")
                    yield Button("Finish", id="finish-button", variant="primary")

            with Horizontal(id="nav"):
                yield Static("└─ ↑↓ MOVE · ←→ NAVIGATE · ENTER SELECT · MOUSE ONLINE ─", id="nav-hint")
                yield Button("Back", id="back")
                yield Button("Next", id="next", variant="primary")

    def on_mount(self) -> None:
        _terminal_cue("boot")
        self.query_one("#auth-button", Button).display = False
        self.query_one("#finish-button", Button).display = False
        self.set_interval(0.12, self._pulse_tick)
        self._render_stepbar()
        self._refresh_openclaw_fields()
        self._refresh_context()
        self.query_one("#mode", Select).focus()

    def _pulse_tick(self) -> None:
        # Textual may deliver one final timer tick while the test/app screen is
        # being torn down. Treat that as normal lifecycle cleanup rather than
        # querying widgets that no longer exist.
        try:
            pulse = self.query_one("#pulse", Static)
            hero_widget = self.query_one("#hero", Static)
        except NoMatches:
            return

        self.animation_tick += 1
        self.pulse_index = (self.pulse_index + 1) % len(self.pulse_frames)
        pulse.update(self.pulse_frames[self.pulse_index])

        hero = self.hero_frames[(self.animation_tick // 2) % len(self.hero_frames)]
        hero_widget.update(
            hero
            + "\n│        INSTALLATION CONTROL DECK         │"
            + "\n╰──────────────────────────────────────────╯"
        )

        scan = self.scan_frames[self.animation_tick % len(self.scan_frames)]
        if self.transition_ticks > 0:
            self.transition_ticks -= 1
            self.query_one("#system-line", Static).update(
                "├─ " + scan + "  switching subsystem ─┤"
            )
        elif self.step == 5 and not self.core_installed:
            self.query_one("#system-line", Static).update(
                "├─ " + scan + "  installation sequence active ─┤"
            )
            self.query_one("#progress-status", Static).update(
                scan + "  " + self.progress_title
            )
        elif self.core_installed:
            self.query_one("#system-line", Static).update(
                "╰─ ●  installation verified // systems nominal ─╯"
            )
        else:
            self.query_one("#system-line", Static).update(
                "├─ " + scan + "  systems ready ─┤"
            )

        if self.animation_tick % 80 == 0 and self.step < 5:
            self.tagline = random.choice(BANTER)
            self.query_one("#tagline", Static).update("‹ " + self.tagline + " ›")

    def _platform_summary(self) -> str:
        return (
            platform.system()
            + " "
            + platform.release()
            + "  ·  "
            + platform.machine()
            + "  ·  bundled runtime"
        )

    def _refresh_openclaw_fields(self) -> None:
        if not self.is_mounted:
            return
        try:
            auth = str(self.query_one("#openclaw-auth", Select).value)
            spec = provider(auth)
            is_custom = auth == "custom-api-key"
            is_universal = auth == "universal-provider"
            is_local = bool(spec and spec.local)
            needs_base = is_custom or is_universal or bool(
                spec and (spec.local or spec.requires_base_url)
            )
            needs_key = is_custom or is_universal or bool(
                spec and spec.credential_env
            )

            self.query_one("#openclaw-provider-key", Input).display = needs_key
            self.query_one("#openclaw-universal-title", Static).display = is_universal
            self.query_one("#openclaw-universal-auth-choice", Input).display = is_universal
            self.query_one("#openclaw-universal-env", Input).display = is_universal
            self.query_one("#openclaw-universal-plugin", Input).display = is_universal

            self.query_one("#openclaw-custom-title", Static).display = needs_base
            self.query_one("#openclaw-custom-base-url", Input).display = needs_base
            self.query_one("#openclaw-custom-model-id", Input).display = (
                is_custom or is_universal or is_local
            )
            self.query_one("#openclaw-custom-provider-id", Input).display = is_custom
            self.query_one("#openclaw-custom-compat", Select).display = is_custom
            self.query_one("#openclaw-custom-image-row", Horizontal).display = is_custom

            plugin = spec.plugin if spec and spec.plugin else ""
            if is_universal:
                plugin = self.query_one(
                    "#openclaw-universal-plugin", Input
                ).value.strip()
            self.query_one(
                "#openclaw-plugin-consent-row", Horizontal
            ).display = bool(plugin)
        except NoMatches:
            return

    def _refresh_context(self) -> None:
        if not self.is_mounted:
            return

        if self.step == 0:
            mode = str(self.query_one("#mode", Select).value)
            text = (
                "Desktop  ·  current-user audio  ·  starts with your login"
                if mode == "desktop"
                else "Server  ·  persistent startup  ·  always-on hardware"
            )
        elif self.step == 1:
            auth = str(self.query_one("#openclaw-auth", Select).value)
            spec = provider(auth)
            if spec:
                suffix = (
                    " · external authorization"
                    if spec.interactive
                    else " · hidden onboarding"
                )
                text = "Brain  ·  " + spec.label + suffix
            elif auth == "custom-api-key":
                text = "Brain  ·  custom compatible API · hidden onboarding"
            elif auth == "universal-provider":
                text = "Brain  ·  universal OpenClaw provider pass-through"
            else:
                text = "Brain  ·  setup deferred · local Jervis remains usable"
        elif self.step == 2:
            mic = self.query_one("#microphone", Select).value
            out = self.query_one("#output", Select).value
            mic_text = "waiting for microphone" if mic is Select.NULL else str(mic)
            out_text = "waiting for output" if out is Select.NULL else "output #" + str(out)
            text = "Audio  ·  " + mic_text + "  →  " + out_text
        elif self.step == 3:
            name = self.query_one("#owner-name", Input).value.strip() or "owner not named yet"
            honorific = str(self.query_one("#honorific", Select).value)
            text = (
                "Identity  ·  "
                + name
                + " · address as "
                + ("ma'am" if honorific == "maam" else "sir")
                + " · passphrase encrypted locally"
            )
        elif self.step == 4:
            text = "Review  ·  nothing is changed until you start installation"
        else:
            text = "Install  ·  staged changes  ·  verification  ·  automatic rollback"

        try:
            self.query_one("#context", Static).update(text)
        except Exception:
            pass

    def _render_stepbar(self) -> None:
        parts = []
        for index, name in enumerate(self.STEPS):
            number = str(index + 1).zfill(2)
            if index < self.step:
                parts.append("✓" + number + " " + name.upper())
            elif index == self.step:
                parts.append("╢" + number + " " + name.upper() + "╟")
            else:
                parts.append("·" + number + " " + name.upper())
        self.query_one("#stepbar", Static).update(" ── ".join(parts))

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
                self.plan.openclaw_accept_risk = bool(
                    self.query_one("#openclaw-risk", Switch).value
                )
                self.plan.openclaw_accept_plugin_capabilities = bool(
                    self.query_one("#openclaw-plugin-capabilities", Switch).value
                )
                self.plan.openclaw_agent_name = self.query_one(
                    "#openclaw-agent-name", Input
                ).value.strip()
                self.plan.openclaw_api_key = self.query_one(
                    "#openclaw-provider-key", Input
                ).value
                self.plan.openclaw_gateway_bind = str(
                    self.query_one("#openclaw-gateway-bind", Select).value
                )
                self.plan.openclaw_gateway_auth = str(
                    self.query_one("#openclaw-gateway-auth", Select).value
                )
                self.plan.openclaw_gateway_secret = self.query_one(
                    "#openclaw-gateway-secret", Input
                ).value
                self.plan.openclaw_daemon_runtime = str(
                    self.query_one("#openclaw-daemon-runtime", Select).value
                )
                self.plan.openclaw_node_manager = str(
                    self.query_one("#openclaw-node-manager", Select).value
                )
                self.plan.openclaw_install_daemon = bool(
                    self.query_one("#openclaw-daemon", Switch).value
                )
                self.plan.openclaw_setup_skills = bool(
                    self.query_one("#openclaw-skills", Switch).value
                )
                self.plan.openclaw_setup_hooks = bool(
                    self.query_one("#openclaw-hooks", Switch).value
                )
                self.plan.openclaw_setup_channels = bool(
                    self.query_one("#openclaw-channels", Switch).value
                )
                self.plan.openclaw_setup_search = bool(
                    self.query_one("#openclaw-search", Switch).value
                )
                self.plan.openclaw_custom_base_url = self.query_one(
                    "#openclaw-custom-base-url", Input
                ).value.strip()
                self.plan.openclaw_custom_model_id = self.query_one(
                    "#openclaw-custom-model-id", Input
                ).value.strip()
                self.plan.openclaw_custom_provider_id = self.query_one(
                    "#openclaw-custom-provider-id", Input
                ).value.strip()
                self.plan.openclaw_custom_compatibility = str(
                    self.query_one("#openclaw-custom-compat", Select).value
                )
                self.plan.openclaw_custom_image_input = bool(
                    self.query_one("#openclaw-custom-image", Switch).value
                )
                self.plan.openclaw_universal_auth_choice = self.query_one(
                    "#openclaw-universal-auth-choice", Input
                ).value.strip()
                self.plan.openclaw_universal_credential_env = self.query_one(
                    "#openclaw-universal-env", Input
                ).value.strip()
                self.plan.openclaw_universal_plugin = self.query_one(
                    "#openclaw-universal-plugin", Input
                ).value.strip()
                self.plan.validate_openclaw()
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
        spec = provider(self.plan.openclaw_auth)
        if spec:
            brain = spec.label
        elif self.plan.openclaw_auth == "custom-api-key":
            brain = "Custom compatible provider"
        elif self.plan.openclaw_auth == "universal-provider":
            brain = (
                "OpenClaw pass-through · "
                + self.plan.openclaw_universal_auth_choice
            )
        else:
            brain = "Configure later"
        lines = [
            "✓  [b]Mode[/b]          " + self.plan.mode.title(),
            "✓  [b]Brain[/b]         " + brain,
            "✓  [b]OpenClaw agent[/b] " + self.plan.openclaw_agent_name,
            "✓  [b]Gateway[/b]       "
            + self.plan.openclaw_gateway_bind
            + " · "
            + self.plan.openclaw_gateway_auth,
            "✓  [b]Provider secret[/b] "
            + ("configured (hidden)" if self.plan.openclaw_api_key else "not required / external auth"),
            "✓  [b]Microphone[/b]    " + microphone,
            "✓  [b]Output[/b]        Device #" + str(self.plan.output_device),
            "✓  [b]Startup[/b]       " + ("Automatic" if self.plan.start_at_boot else "Manual"),
            "✓  [b]Owner[/b]         " + self.plan.owner_name,
            "✓  [b]Address as[/b]    " + ("Ma'am" if self.plan.honorific == "maam" else "Sir"),
            "✓  [b]Authentication[/b] Local passphrase configured",
        ]
        self.query_one("#review", Static).update("\n".join(lines))

    @on(Select.Changed)
    def selection_changed(self, event: Select.Changed) -> None:
        if event.select.id == "openclaw-auth":
            self._refresh_openclaw_fields()
        self._refresh_context()

    @on(Switch.Changed)
    def switch_changed(self, event: Switch.Changed) -> None:
        del event
        self._refresh_context()

    @on(Input.Changed)
    def input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "openclaw-universal-plugin":
            self._refresh_openclaw_fields()
        if event.input.id in {
            "owner-name",
            "openclaw-universal-auth-choice",
        }:
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
            self.call_from_thread(
                self._speaker_test_complete,
            )
        except Exception as exc:
            self.call_from_thread(
                self.notify,
                str(exc),
                title="Speaker test failed",
                severity="error",
            )

    def _speaker_test_complete(self) -> None:
        self.query_one("#audio-meter", Static).update(
            "OUTPUT TEST  ·  ✓ tone played successfully"
        )
        self.notify("Output test passed.", title="Audio")

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
                configure_interactive_authorization(
                    Path(self.outcome.openclaw_cli),
                    self.plan,
                )
        except Exception as exc:
            _terminal_cue("attention")
            self.query_one("#error-mark", Static).update(
                "╭─ ! OPENCLAW ATTENTION REQUIRED ─╮\n"
                + str(exc)
                + "\n╰─ Jervis core remains installed ─╯"
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

    def _cycle_focused_select(self, direction: int) -> bool:
        focused = self.screen.focused
        if not isinstance(focused, Select):
            return False

        values = self.select_values.get(str(focused.id or ""), [])
        if not values:
            return False

        current = focused.value
        try:
            index = values.index(current)
        except ValueError:
            index = 0
        focused.value = values[(index + direction) % len(values)]
        self._refresh_context()
        return True

    def action_back(self) -> None:
        focused = self.screen.focused
        if isinstance(focused, Switch):
            focused.value = False
            self._refresh_context()
            return
        if self._cycle_focused_select(-1):
            return
        if 0 < self.step < 5:
            self._switch(self.step - 1)

    def action_forward(self) -> None:
        focused = self.screen.focused
        if isinstance(focused, Switch):
            focused.value = True
            self._refresh_context()
            return
        if self._cycle_focused_select(1):
            return
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
            _terminal_cue("attention")
            self.notify(str(exc), title="Review", severity="warning")
            return
        _terminal_cue("install")
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
        _terminal_cue("attention")
        self.query_one(LoadingIndicator).display = False
        self.query_one("#error-mark", Static).update(
            "╭─ ! ATTENTION // INSTALL HALTED ─╮\n"
            + message
            + "\n╰─ rollback boundary preserved ──╯"
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
        needs_auth = bool(outcome.openclaw_cli and outcome.openclaw_needs_auth)
        if needs_auth:
            _terminal_cue("attention")
            self.query_one("#progress-status", Static).update(
                "Jervis is installed. External account authorization remains."
            )
            self.query_one("#auth-button", Button).display = True
        else:
            self._show_done()

    def _show_done(self) -> None:
        _terminal_cue("complete")
        self.query_one("#auth-button", Button).display = False
        self.query_one("#progress-status", Static).update(
            "╰─ INSTALLATION COMPLETE // SYSTEMS NOMINAL ─╯"
        )
        self.query_one("#done-mark", Static).update(
            "╭──────────── ✓ JERVIS " + __version__ + " READY ────────────╮\n"
            "│      VOICE · IDENTITY · MEMORY · OPENCLAW ONLINE      │\n"
            "╰──────────────────────────────────────────────────────╯"
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
