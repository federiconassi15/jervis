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
from textual import events, on, work
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
from .openclaw_setup import find_openclaw
from .openclaw_wizard import OpenClawWizardBridge, WizardResult
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
        background: #090d12;
        color: #e6edf3;
        overflow: hidden;
    }

    #frame {
        width: 100%;
        height: 100%;
        background: #090d12;
    }

    #install-shell {
        width: 100%;
        height: 100%;
    }

    #sidebar {
        width: 26;
        min-width: 22;
        height: 100%;
        background: #0d141b;
        border-right: solid #26313b;
        padding: 1 1;
    }

    #brand {
        height: 2;
        color: #f0f6fc;
        text-style: bold;
    }

    #brand-sub {
        height: 2;
        color: #7d8b99;
        border-bottom: solid #26313b;
        margin-bottom: 1;
    }

    #stepbar {
        height: 1fr;
        color: #8b98a5;
        padding-top: 1;
    }

    #sidebar-footer {
        height: auto;
        color: #62707d;
        border-top: solid #26313b;
        padding-top: 1;
    }

    #main-pane {
        width: 1fr;
        height: 100%;
        min-width: 30;
        padding: 1 2;
        background: #090d12;
    }

    #compact-stage {
        display: none;
        height: 1;
        color: #58c7ff;
        text-style: bold;
        margin-bottom: 1;
    }

    #context {
        height: auto;
        min-height: 2;
        max-height: 4;
        color: #8b98a5;
        margin-bottom: 1;
    }

    #pages {
        width: 100%;
        height: 1fr;
        min-height: 1;
        overflow: hidden;
    }

    .page {
        width: 100%;
        height: 100%;
        padding: 0;
        overflow-y: auto;
        scrollbar-size-vertical: 1;
    }

    .title {
        height: auto;
        min-height: 2;
        color: #f0f6fc;
        text-style: bold;
        margin-bottom: 1;
    }

    .hint {
        height: auto;
        color: #8b98a5;
        margin-bottom: 1;
    }

    .card {
        height: auto;
        background: #0d141b;
        border: solid #26313b;
        padding: 1 2;
        margin: 1 0;
    }

    .choice-row {
        width: 100%;
        height: auto;
        layout: horizontal;
        margin: 1 0;
    }

    Button.choice {
        width: 1fr;
        min-width: 18;
        height: 5;
        margin-right: 1;
        content-align: left middle;
        text-align: left;
        background: #0d141b;
        color: #d6dee6;
        border: solid #26313b;
        padding: 0 1;
    }

    Button.choice:hover,
    Button.choice:focus {
        background: #111c26;
        border: solid #58c7ff;
        color: #ffffff;
    }

    Button.choice.selected {
        background: #102432;
        border: solid #58c7ff;
        color: #ffffff;
        text-style: bold;
    }

    Select, Input {
        width: 100%;
        margin: 1 0;
        background: #0d141b;
        border: tall #26313b;
    }

    Select:focus, Input:focus {
        border: tall #58c7ff;
        background: #111c26;
    }

    Horizontal {
        height: auto;
        min-height: 1;
    }

    Switch {
        margin-left: 1;
    }

    Button {
        min-width: 10;
        margin-right: 1;
        background: #111820;
        color: #d6dee6;
        border: solid #26313b;
    }

    Button:hover, Button:focus {
        background: #162431;
        border: solid #58c7ff;
        color: #ffffff;
    }

    Button.-primary {
        background: #0d5f84;
        border: solid #58c7ff;
        color: #ffffff;
    }

    #nav {
        width: 100%;
        height: 4;
        border-top: solid #26313b;
        padding-top: 1;
        align: right middle;
    }

    #nav-hint {
        width: 1fr;
        min-width: 0;
        color: #62707d;
        content-align: left middle;
        text-overflow: ellipsis;
    }

    #audio-meter {
        height: auto;
        min-height: 2;
        color: #7dd3fc;
        background: #0d141b;
        border: solid #26313b;
        padding: 0 1;
        margin: 1 0;
    }

    #progress-status {
        height: auto;
        min-height: 2;
        color: #d6dee6;
        text-style: bold;
    }

    #progress-detail {
        height: auto;
        min-height: 2;
        max-height: 6;
        color: #8b98a5;
    }

    ProgressBar {
        width: 100%;
        margin: 1 0;
    }

    #done-mark, #error-mark {
        height: auto;
        min-height: 2;
        margin: 1 0;
        text-style: bold;
    }

    #done-mark { color: #75e0a7; }
    #error-mark { color: #ff8e9f; }

    #review {
        height: auto;
        background: #0d141b;
        border: solid #26313b;
        padding: 1 2;
        margin: 1 0;
    }

    #frame.compact #sidebar {
        width: 21;
        min-width: 18;
        padding: 1 0;
    }

    #frame.compact #sidebar-footer {
        display: none;
    }

    #frame.compact #main-pane {
        padding: 1 1;
    }

    #frame.compact Button.choice {
        height: 4;
    }

    #frame.narrow #sidebar {
        display: none;
    }

    #frame.narrow #compact-stage {
        display: block;
    }

    #frame.narrow #main-pane {
        padding: 1 1;
        min-width: 1;
    }

    #frame.narrow .choice-row {
        layout: vertical;
    }

    #frame.narrow Button.choice {
        width: 100%;
        margin-right: 0;
        margin-bottom: 1;
    }

    #frame.short #context {
        display: none;
    }

    #frame.short #nav-hint {
        display: none;
    }

    #frame.short #nav {
        height: 3;
        padding-top: 0;
        align: center middle;
    }

    #frame.short #nav Button {
        height: 1;
        border: none;
        padding: 0 1;
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
        self.compact_mode = False
        self.tiny_mode = False
        self.mode_choice = "desktop"
        self.openclaw_setup_choice = "wizard"
        self.progress_title = "Preparing…"
        self.progress_detail = ""
        self.inputs, self.outputs, self.androids = self._detect_audio()
        self.select_values = {
            "microphone": [value for _label, value in self.inputs],
            "output": [value for _label, value in self.outputs],
            "honorific": ["sir", "maam"],
        }
        self.openclaw = find_openclaw()
        self.openclaw_wizard: OpenClawWizardBridge | None = None
        self.openclaw_wizard_step: dict | None = None
        self.openclaw_wizard_option_values: list[object] = []

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
            with Horizontal(id="install-shell"):
                with Container(id="sidebar"):
                    yield Static("JERVIS", id="brand")
                    yield Static("SETUP  ·  " + __version__, id="brand-sub")
                    yield Static("", id="stepbar")
                    yield Static(
                        self._platform_summary() + "\n\n↑↓ move  ·  Enter select",
                        id="sidebar-footer",
                    )

                with Container(id="main-pane"):
                    yield Static("", id="compact-stage")
                    yield Static("", id="context")

                    with ContentSwitcher(initial="page-mode", id="pages"):
                        with VerticalScroll(classes="page", id="page-mode"):
                            yield Static("Where should Jervis live?", classes="title")
                            yield Static(
                                "Choose the environment Jervis should optimize itself for. "
                                "Both options use the same runtime.",
                                classes="hint",
                            )
                            with Container(classes="choice-row"):
                                yield Button(
                                    "Desktop\nEveryday PC or Mac\nUses your normal login and audio session",
                                    id="mode-desktop",
                                    classes="choice selected",
                                )
                                yield Button(
                                    "Server\nAlways-on machine / NUC\nPersistent startup and headless-friendly behaviour",
                                    id="mode-server",
                                    classes="choice",
                                )
                            yield Static(
                                "Nothing is installed until the Review page.",
                                classes="hint",
                            )

                        with VerticalScroll(classes="page", id="page-brain"):
                            yield Static("Connect the OpenClaw brain", classes="title")
                            yield Static(
                                "Jervis can render OpenClaw's own live setup flow without "
                                "hard-coding providers or API choices.",
                                classes="hint",
                            )
                            yield Static(
                                (
                                    "OpenClaw detected  ·  " + str(self.openclaw)
                                    if self.openclaw
                                    else "OpenClaw is not installed yet"
                                ),
                                classes="card",
                                id="openclaw-status",
                            )
                            with Container(classes="choice-row"):
                                yield Button(
                                    "Guided setup\nRecommended\nUse OpenClaw's live provider/API wizard",
                                    id="brain-wizard",
                                    classes="choice selected",
                                )
                                yield Button(
                                    "Configure later\nSkip brain setup for now\nLocal Jervis features still install",
                                    id="brain-later",
                                    classes="choice",
                                )
                            with Horizontal(classes="card"):
                                yield Label("Install OpenClaw automatically if missing")
                                yield Switch(value=True, id="openclaw-install")

                        with VerticalScroll(classes="page", id="page-audio"):
                            yield Static("Choose Jervis audio", classes="title")
                            yield Static(
                                "Select the microphone and output Jervis should use.",
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
                            yield Static("Create the local owner", classes="title")
                            yield Static(
                                "Identity, permissions and trusted sessions stay local to Jervis.",
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
                                "The passphrase is never shown in Review or normal logs.",
                                classes="hint",
                            )

                        with VerticalScroll(classes="page", id="page-review"):
                            yield Static("Review before Jervis changes anything", classes="title")
                            yield Static("", id="review")
                            yield Static(
                                "The install engine is transactional and keeps rollback boundaries.",
                                classes="hint",
                            )

                        with VerticalScroll(classes="page", id="page-install"):
                            yield Static("Installing Jervis", classes="title")
                            yield LoadingIndicator()
                            yield Static("Preparing…", id="progress-status")
                            yield Static("", id="progress-detail")
                            yield ProgressBar(
                                total=TOTAL_STEPS,
                                show_eta=False,
                                id="progress",
                            )
                            yield Static("", id="error-mark")

                            yield Static(
                                "",
                                id="openclaw-wizard-title",
                                classes="title",
                                markup=False,
                            )
                            yield Static(
                                "",
                                id="openclaw-wizard-message",
                                classes="card",
                                markup=False,
                            )
                            yield Static(
                                "",
                                id="openclaw-wizard-options",
                                classes="hint",
                                markup=False,
                            )
                            yield Select(
                                [("Waiting for OpenClaw…", "0")],
                                allow_blank=True,
                                id="openclaw-wizard-select",
                            )
                            yield Input(id="openclaw-wizard-input")
                            with Horizontal(
                                classes="card",
                                id="openclaw-wizard-confirm-row",
                            ):
                                yield Label("Confirm")
                                yield Switch(
                                    value=False,
                                    id="openclaw-wizard-confirm",
                                )
                            yield Button(
                                "Continue",
                                id="openclaw-wizard-next",
                                variant="primary",
                            )

                            yield Static("", id="done-mark")
                            yield Button(
                                "Retry OpenClaw setup",
                                id="auth-button",
                                variant="primary",
                            )
                            yield Button(
                                "Finish",
                                id="finish-button",
                                variant="primary",
                            )

                    with Horizontal(id="nav"):
                        yield Static(
                            "↑↓ move  ·  Enter select  ·  Tab next field",
                            id="nav-hint",
                        )
                        yield Button("Back", id="back")
                        yield Button("Next", id="next", variant="primary")

    def _apply_responsive_layout(self, width: int, height: int) -> None:
        if not self.is_mounted:
            return
        frame = self.query_one("#frame", Container)
        compact = width < 86
        narrow = width < 58
        short = height < 20
        self.compact_mode = compact
        self.tiny_mode = narrow
        frame.set_class(compact, "compact")
        frame.set_class(narrow, "narrow")
        frame.set_class(short, "short")
        self._render_stepbar()

    def on_resize(self, event: events.Resize) -> None:
        self._apply_responsive_layout(event.size.width, event.size.height)

    def on_mount(self) -> None:
        _terminal_cue("boot")
        self.query_one("#auth-button", Button).display = False
        self.query_one("#finish-button", Button).display = False
        self._hide_openclaw_wizard_controls()
        self._apply_responsive_layout(self.size.width, self.size.height)
        self._select_mode("desktop")
        self._select_brain_setup("wizard")
        self._render_stepbar()
        self._refresh_context()
        self.query_one("#mode-desktop", Button).focus()

    def _hide_openclaw_wizard_controls(self) -> None:
        for selector in (
            "#openclaw-wizard-title",
            "#openclaw-wizard-message",
            "#openclaw-wizard-options",
            "#openclaw-wizard-select",
            "#openclaw-wizard-input",
            "#openclaw-wizard-confirm-row",
            "#openclaw-wizard-next",
        ):
            try:
                self.query_one(selector).display = False
            except NoMatches:
                pass

    def _show_openclaw_wizard_shell(self) -> None:
        self.query_one("#openclaw-wizard-title").display = True
        self.query_one("#openclaw-wizard-message").display = True

    def _close_openclaw_wizard(self) -> None:
        bridge = self.openclaw_wizard
        self.openclaw_wizard = None
        self.openclaw_wizard_step = None
        if bridge is not None:
            try:
                bridge.close()
            except Exception:
                pass

    def _pulse_tick(self) -> None:
        # 7.4 deliberately avoids an animated installer repaint loop.
        return

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
            text = (
                "Desktop uses your normal login/audio session."
                if self.mode_choice == "desktop"
                else "Server is tuned for persistent startup on an always-on machine."
            )
        elif self.step == 1:
            text = (
                "OpenClaw guided setup will run inside Jervis."
                if self.openclaw_setup_choice == "wizard"
                else "OpenClaw setup is deferred; local Jervis features still install."
            )
        elif self.step == 2:
            mic = self.query_one("#microphone", Select).value
            out = self.query_one("#output", Select).value
            mic_text = "choose a microphone" if mic is Select.NULL else str(mic)
            out_text = "choose an output" if out is Select.NULL else "output #" + str(out)
            text = "Audio  ·  " + mic_text + "  →  " + out_text
        elif self.step == 3:
            name = self.query_one("#owner-name", Input).value.strip() or "owner not named yet"
            text = "Identity  ·  " + name + "  ·  local authentication"
        elif self.step == 4:
            text = "Review every choice before the transactional install begins."
        else:
            text = "Install  ·  snapshot  ·  apply  ·  verify  ·  rollback if needed"

        try:
            self.query_one("#context", Static).update(text)
        except Exception:
            pass

    def _render_stepbar(self) -> None:
        if not self.is_mounted:
            return
        labels = ["Deployment", "OpenClaw", "Audio", "Identity", "Review", "Install"]
        lines = []
        for index, label in enumerate(labels):
            if index < self.step:
                marker = "✓"
            elif index == self.step:
                marker = "▸"
            else:
                marker = " "
            lines.append(marker + "  " + label)
        self.query_one("#stepbar", Static).update("\n".join(lines))
        try:
            self.query_one("#compact-stage", Static).update(
                "SETUP  /  " + labels[self.step].upper()
            )
        except Exception:
            pass

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
        self._render_stepbar()
        self._refresh_context()
        focus_targets = {
            0: "#mode-desktop" if self.mode_choice == "desktop" else "#mode-server",
            1: "#brain-wizard" if self.openclaw_setup_choice == "wizard" else "#brain-later",
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
                self.plan.mode = self.mode_choice
                if self.plan.mode == "server":
                    self.query_one("#autostart", Switch).value = True
            elif self.step == 1:
                self.plan.openclaw_setup = self.openclaw_setup_choice
                self.plan.install_openclaw = bool(
                    self.query_one("#openclaw-install", Switch).value
                )
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
        brain = (
            "Full OpenClaw wizard · providers/APIs supplied live by OpenClaw"
            if self.plan.openclaw_setup == "wizard"
            else "Configure OpenClaw later"
        )
        lines = [
            "✓  [b]Mode[/b]          " + self.plan.mode.title(),
            "✓  [b]Brain[/b]         " + brain,
            "✓  [b]Microphone[/b]    " + microphone,
            "✓  [b]Output[/b]        Device #" + str(self.plan.output_device),
            "✓  [b]Startup[/b]       " + ("Automatic" if self.plan.start_at_boot else "Manual"),
            "✓  [b]Owner[/b]         " + self.plan.owner_name,
            "✓  [b]Address as[/b]    " + ("Ma'am" if self.plan.honorific == "maam" else "Sir"),
            "✓  [b]Authentication[/b] Local passphrase configured",
        ]
        self.query_one("#review", Static).update("\n".join(lines))

    def _select_mode(self, value: str) -> None:
        if value not in {"desktop", "server"}:
            return
        self.mode_choice = value
        self.plan.mode = value
        self.query_one("#mode-desktop", Button).set_class(
            value == "desktop", "selected"
        )
        self.query_one("#mode-server", Button).set_class(
            value == "server", "selected"
        )
        if value == "server":
            self.query_one("#autostart", Switch).value = True
        self._refresh_context()

    def _select_brain_setup(self, value: str) -> None:
        if value not in {"wizard", "later"}:
            return
        self.openclaw_setup_choice = value
        self.plan.openclaw_setup = value
        self.query_one("#brain-wizard", Button).set_class(
            value == "wizard", "selected"
        )
        self.query_one("#brain-later", Button).set_class(
            value == "later", "selected"
        )
        self._refresh_context()

    @on(Button.Pressed, "#mode-desktop")
    def mode_desktop_pressed(self) -> None:
        self._select_mode("desktop")

    @on(Button.Pressed, "#mode-server")
    def mode_server_pressed(self) -> None:
        self._select_mode("server")

    @on(Button.Pressed, "#brain-wizard")
    def brain_wizard_pressed(self) -> None:
        self._select_brain_setup("wizard")

    @on(Button.Pressed, "#brain-later")
    def brain_later_pressed(self) -> None:
        self._select_brain_setup("later")

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

    def _render_openclaw_wizard_step(self, step: dict) -> None:
        self.openclaw_wizard_step = step
        self._hide_openclaw_wizard_controls()
        self._show_openclaw_wizard_shell()

        step_type = str(step.get("type", "note"))
        title = str(step.get("title") or "OPENCLAW GUIDED SETUP")
        message = str(step.get("message") or "")
        self.query_one("#openclaw-wizard-title", Static).update(
            "┌─ OPENCLAW // " + title.upper() + " ─┐"
        )
        self.query_one("#openclaw-wizard-message", Static).update(message)
        self.query_one("#progress-status", Static).update(
            "OpenClaw setup · " + step_type
        )

        next_button = self.query_one("#openclaw-wizard-next", Button)
        options_text = self.query_one("#openclaw-wizard-options", Static)
        options_text.update("")
        self.openclaw_wizard_option_values = []
        self.select_values.pop("openclaw-wizard-select", None)

        if step_type == "text":
            field = self.query_one("#openclaw-wizard-input", Input)
            field.display = True
            field.password = bool(step.get("sensitive", False))
            initial = step.get("initialValue")
            field.value = "" if initial is None else str(initial)
            field.placeholder = str(step.get("placeholder") or "")
            next_button.label = "Submit"
            next_button.display = True
            field.focus()
            return

        if step_type == "select":
            raw_options = step.get("options")
            options = raw_options if isinstance(raw_options, list) else []
            labels: list[tuple[str, str]] = []
            values: list[object] = []
            initial_index = 0
            initial = step.get("initialValue")
            for index, option in enumerate(options):
                if not isinstance(option, dict):
                    continue
                value = option.get("value")
                label = str(option.get("label") or value or ("Option " + str(index + 1)))
                hint = str(option.get("hint") or "").strip()
                if hint:
                    label += " · " + hint
                token = str(len(values))
                labels.append((label, token))
                values.append(value)
                if value == initial:
                    initial_index = len(values) - 1

            if not labels:
                labels = [("No options returned by OpenClaw", "0")]
                values = [None]

            control = self.query_one("#openclaw-wizard-select", Select)
            control.set_options(labels)
            control.value = str(min(initial_index, len(values) - 1))
            control.display = True
            self.openclaw_wizard_option_values = values
            self.select_values["openclaw-wizard-select"] = [
                str(i) for i in range(len(values))
            ]
            next_button.label = "Select"
            next_button.display = True
            control.focus()
            return

        if step_type == "confirm":
            control = self.query_one("#openclaw-wizard-confirm", Switch)
            control.value = bool(step.get("initialValue", False))
            self.query_one("#openclaw-wizard-confirm-row").display = True
            next_button.label = "Confirm"
            next_button.display = True
            control.focus()
            return

        if step_type == "multiselect":
            raw_options = step.get("options")
            options = raw_options if isinstance(raw_options, list) else []
            values: list[object] = []
            lines: list[str] = []
            initial_values = step.get("initialValue")
            selected = initial_values if isinstance(initial_values, list) else []
            selected_numbers: list[str] = []
            for index, option in enumerate(options, start=1):
                if not isinstance(option, dict):
                    continue
                value = option.get("value")
                values.append(value)
                label = str(option.get("label") or value or ("Option " + str(index)))
                hint = str(option.get("hint") or "").strip()
                lines.append(
                    str(index) + ". " + label + ((" · " + hint) if hint else "")
                )
                if value in selected:
                    selected_numbers.append(str(index))

            self.openclaw_wizard_option_values = values
            options_text.update("\n".join(lines))
            options_text.display = True
            field = self.query_one("#openclaw-wizard-input", Input)
            field.password = False
            field.placeholder = "Comma-separated choices · e.g. 1,3,5"
            field.value = ",".join(selected_numbers)
            field.display = True
            next_button.label = "Apply selections"
            next_button.display = True
            field.focus()
            return

        if step_type == "progress":
            self.query_one("#progress-detail", Static).update(
                message or "OpenClaw is working…"
            )
            self.set_timer(0.05, self._poll_openclaw_wizard)
            return

        # note and action steps stay fully inside Jervis. OAuth/device-code
        # URLs/codes delivered by OpenClaw appear in the message above.
        next_button.label = "Continue"
        next_button.display = True
        next_button.focus()

    def _openclaw_wizard_result(self, result: WizardResult) -> None:
        if result.done:
            if result.status == "done":
                if self.outcome is not None:
                    self.outcome.openclaw_configured = True
                    self.outcome.openclaw_needs_wizard = False
                self._close_openclaw_wizard()
                self._hide_openclaw_wizard_controls()
                self.query_one("#progress-detail", Static).update(
                    "OpenClaw setup completed through the Jervis control deck."
                )
                self._show_done()
                return
            self._openclaw_wizard_failed(
                result.error or ("OpenClaw wizard ended with status " + result.status)
            )
            return

        if result.step is None:
            self._openclaw_wizard_failed(
                "OpenClaw returned no setup step and did not report completion."
            )
            return
        self._render_openclaw_wizard_step(result.step)

    def _openclaw_wizard_failed(self, message: str) -> None:
        _terminal_cue("attention")
        self._close_openclaw_wizard()
        self._hide_openclaw_wizard_controls()
        self.query_one("#error-mark", Static).update(
            "╭─ ! OPENCLAW SETUP NEEDS ATTENTION ─╮\n"
            + message[-3000:]
            + "\n╰─ Jervis core remains installed ────╯"
        )
        self.query_one("#progress-status", Static).update(
            "OpenClaw guided setup did not finish."
        )
        self.query_one("#progress-detail", Static).update(
            "Earlier OpenClaw answers may already be saved. Retry the upstream "
            "wizard, or finish and configure it later."
        )
        self.query_one("#auth-button", Button).display = True
        self.query_one("#finish-button", Button).display = True

    @work(thread=True, exclusive=True, group="openclaw-wizard-start")
    def _begin_openclaw_wizard_worker(self) -> None:
        outcome = self.outcome
        if not outcome or not outcome.openclaw_cli:
            self.call_from_thread(
                self._openclaw_wizard_failed,
                "OpenClaw CLI is unavailable.",
            )
            return

        bridge = OpenClawWizardBridge(Path(outcome.openclaw_cli))
        try:
            result = bridge.start()
        except Exception as exc:
            try:
                bridge.close()
            except Exception:
                pass
            self.call_from_thread(self._openclaw_wizard_failed, str(exc))
            return

        self.openclaw_wizard = bridge
        self.call_from_thread(self._openclaw_wizard_result, result)

    def _begin_openclaw_wizard(self) -> None:
        self.query_one("#auth-button", Button).display = False
        self.query_one("#finish-button", Button).display = False
        self.query_one("#error-mark", Static).update("")
        self.query_one("#progress-status", Static).update(
            "Starting OpenClaw guided setup inside Jervis…"
        )
        self.query_one("#progress-detail", Static).update(
            "Loading the live upstream provider/API/channel/skills wizard."
        )
        self._begin_openclaw_wizard_worker()

    @work(thread=True, exclusive=True, group="openclaw-wizard-next")
    def _advance_openclaw_wizard_worker(
        self,
        step_id: str | None,
        value,
    ) -> None:
        bridge = self.openclaw_wizard
        if bridge is None:
            self.call_from_thread(
                self._openclaw_wizard_failed,
                "OpenClaw wizard connection is not active.",
            )
            return
        try:
            result = bridge.next(step_id, value)
        except Exception as exc:
            self.call_from_thread(self._openclaw_wizard_failed, str(exc))
            return
        self.call_from_thread(self._openclaw_wizard_result, result)

    def _poll_openclaw_wizard(self) -> None:
        self._advance_openclaw_wizard_worker(None, None)

    @on(Button.Pressed, "#openclaw-wizard-next")
    def openclaw_wizard_next_pressed(self) -> None:
        step = self.openclaw_wizard_step
        if not step:
            return

        step_id = str(step.get("id") or "")
        step_type = str(step.get("type") or "note")
        value = None

        try:
            if step_type == "text":
                value = self.query_one("#openclaw-wizard-input", Input).value
            elif step_type == "select":
                token = self.query_one("#openclaw-wizard-select", Select).value
                if token is Select.NULL:
                    raise ValueError("Choose an OpenClaw option.")
                index = int(str(token))
                value = self.openclaw_wizard_option_values[index]
            elif step_type == "confirm":
                value = bool(
                    self.query_one("#openclaw-wizard-confirm", Switch).value
                )
            elif step_type == "multiselect":
                raw = self.query_one("#openclaw-wizard-input", Input).value.strip()
                indexes: list[int] = []
                if raw:
                    for item in raw.split(","):
                        number = int(item.strip())
                        index = number - 1
                        if index < 0 or index >= len(self.openclaw_wizard_option_values):
                            raise ValueError(
                                "Multiselect choices must use the numbers shown above."
                            )
                        if index not in indexes:
                            indexes.append(index)
                value = [self.openclaw_wizard_option_values[index] for index in indexes]
            elif step_type == "action":
                value = step.get("initialValue", True)
        except Exception as exc:
            self.notify(str(exc), title="OpenClaw setup", severity="warning")
            return

        self.query_one("#openclaw-wizard-next", Button).display = False
        self._advance_openclaw_wizard_worker(step_id, value)

    @on(Button.Pressed, "#auth-button")
    def auth_button_pressed(self) -> None:
        self._close_openclaw_wizard()
        self._begin_openclaw_wizard()

    @on(Button.Pressed, "#finish-button")
    def finish_pressed(self) -> None:
        self._close_openclaw_wizard()
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
        self._close_openclaw_wizard()
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

        if outcome.openclaw_cli and outcome.openclaw_needs_wizard:
            self._begin_openclaw_wizard()
        else:
            self._show_done()

    def _show_done(self) -> None:
        self._close_openclaw_wizard()
        self._hide_openclaw_wizard_controls()
        _terminal_cue("complete")
        self.query_one("#auth-button", Button).display = False
        self.query_one("#progress-status", Static).update(
            "╰─ INSTALLATION COMPLETE // SYSTEMS NOMINAL ─╯"
        )
        openclaw_state = (
            "OPENCLAW ONLINE"
            if self.outcome is not None and self.outcome.openclaw_configured
            else "OPENCLAW DEFERRED"
        )
        self.query_one("#done-mark", Static).update(
            "╭──────────── ✓ JERVIS " + __version__ + " READY ────────────╮\n"
            "│      VOICE · IDENTITY · MEMORY · "
            + openclaw_state
            + "      │\n"
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
