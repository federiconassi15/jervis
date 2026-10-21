"""Plain, accessible terminal entry points for Jervis 8.

No curses, Textual, terminal sizing, mouse events, or repaint loop is required.
The existing transactional install engine and CLI operations remain authoritative.
"""

from __future__ import annotations

import getpass
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable

from .install_plan import InstallPlan
from .version import __version__

Answer = Callable[[str], str]
Secret = Callable[[str], str]


class Cancelled(Exception):
    """The operator intentionally left a prompt without changing the system."""


def _terminal_required() -> None:
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise RuntimeError(
            "Interactive setup needs a terminal. Open a terminal and run 'jervis install'."
        )


def _choice(title: str, options: list[tuple[str, str]], default: int,
            ask: Answer = input) -> str:
    """Return the selected value. Empty input accepts a visible, numbered default."""
    if not options or not 1 <= default <= len(options):
        raise ValueError("Invalid choice list.")
    print("\n" + title)
    for number, (label, _value) in enumerate(options, 1):
        suffix = " (default)" if number == default else ""
        print(f"  {number}. {label}{suffix}")
    while True:
        answer = ask(f"Choice [1-{len(options)}; q to cancel]: ").strip()
        if answer.lower() in {"q", "quit", "cancel"}:
            raise Cancelled()
        if not answer:
            return options[default - 1][1]
        if answer.isascii() and answer.isdecimal() and 1 <= int(answer) <= len(options):
            return options[int(answer) - 1][1]
        print("Enter one of the displayed numbers, or q to cancel.")


def _yes_no(question: str, *, default: bool, ask: Answer = input) -> bool:
    hint = "[Y/n]" if default else "[y/N]"
    while True:
        answer = ask(f"{question} {hint}: ").strip().lower()
        if answer in {"q", "quit", "cancel"}:
            raise Cancelled()
        if not answer:
            return default
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no"}:
            return False
        print("Answer y or n, or q to cancel.")


def _owner(ask: Answer, secret: Secret) -> tuple[str, str]:
    while True:
        name = ask("Your name (q to cancel): ").strip()
        if name.lower() in {"q", "quit", "cancel"}:
            raise Cancelled()
        if name:
            break
        print("A name is required.")

    while True:
        passphrase = secret("Local Jervis passphrase (8+ characters): ")
        if len(passphrase) < 8:
            print("Use at least 8 characters.")
            continue
        if secret("Confirm passphrase: ") == passphrase:
            return name, passphrase
        print("Passphrases did not match; try again.")


def _devices() -> tuple[list, list, int | None, int | None]:
    from .audio.devices import default_devices, list_devices

    devices = list_devices()
    default_input, default_output = default_devices()
    inputs = [device for device in devices if device.inputs > 0]
    outputs = [device for device in devices if device.outputs > 0]
    return inputs, outputs, default_input, default_output


def _select_device(title: str, devices: list, default_index: int | None,
                   ask: Answer) -> int:
    if not devices:
        raise RuntimeError(f"No {title.lower()} detected. Connect one and retry setup.")
    default = next(
        (n for n, item in enumerate(devices, 1) if item.index == default_index), 1
    )
    options = [
        (f"{item.name} ({item.hostapi})", str(item.index))
        for item in devices
    ]
    return int(_choice(title, options, default, ask))


def _android_serial(ask: Answer) -> str | None:
    from .prereqs import find_adb

    adb = find_adb()
    serials: list[str] = []
    if adb:
        try:
            result = subprocess.run(
                [str(adb), "devices"], capture_output=True, text=True, timeout=5,
                check=False,
            )
            if result.returncode == 0:
                serials = [
                    line.split("\t", 1)[0]
                    for line in result.stdout.splitlines()
                    if line.endswith("\tdevice")
                ]
        except (OSError, subprocess.TimeoutExpired):
            pass
    if not serials:
        print("No authorized Android device detected yet. Connect it before installation.")
        return None
    choices = [(f"Android phone {serial}", serial) for serial in serials]
    return _choice("Select Android microphone", choices, 1, ask)


def make_plan(ask: Answer = input, secret: Secret = getpass.getpass) -> InstallPlan:
    """Ask questions only; no changes to the host are made here."""
    plan = InstallPlan()
    plan.mode = _choice(
        "Where will Jervis run?",
        [("Desktop or laptop", "desktop"), ("Always-on server", "server")],
        1, ask,
    )
    brain = _choice(
        "OpenClaw setup",
        [
            ("Install/reuse OpenClaw, then guide me through onboarding", "wizard"),
            ("Install/reuse OpenClaw, configure later", "later"),
            ("Skip OpenClaw installation for now", "skip"),
        ],
        1, ask,
    )
    plan.install_openclaw = brain != "skip"
    plan.openclaw_setup = "wizard" if brain == "wizard" else "later"

    source = _choice(
        "Microphone source",
        [("Computer microphone", "desktop"), ("Android phone via ADB", "android")],
        1, ask,
    )
    plan.source_kind = source
    try:
        inputs, outputs, default_input, default_output = _devices()
    except Exception as exc:
        raise RuntimeError(
            "Could not list audio devices. Check your audio driver and run 'jervis doctor'."
        ) from exc

    if source == "desktop":
        plan.input_device = _select_device("Microphone", inputs, default_input, ask)
    else:
        plan.android_serial = _android_serial(ask)
    plan.output_device = _select_device("Speaker / output", outputs, default_output, ask)

    plan.owner_name, plan.passphrase = _owner(ask, secret)
    plan.honorific = _choice(
        "How should Jervis address you?",
        [("Sir", "sir"), ("Ma'am", "maam")],
        1, ask,
    )
    plan.start_at_boot = _yes_no(
        "Start Jervis automatically on boot?", default=True, ask=ask
    )
    plan.validate()
    return plan


def _launcher() -> Path:
    override = os.environ.get("JERVIS_LAUNCHER_PATH")
    if override:
        path = Path(override).expanduser()
        if not path.is_file():
            raise RuntimeError("JERVIS_LAUNCHER_PATH does not exist: " + str(path))
        return path
    found = shutil.which("jervis")
    if found:
        return Path(found)
    raise RuntimeError(
        "The Jervis launcher is missing. Install Jervis first or set "
        "JERVIS_LAUNCHER_PATH to the native executable."
    )


def _progress(step: int, total: int, title: str, detail: str) -> None:
    print(f"[{step}/{total}] {title}")
    if detail:
        print("    " + detail)


def install() -> int:
    """Simple, line-oriented installer built around the existing transaction engine."""
    try:
        _terminal_required()
        print(f"\nJervis {__version__} — setup")
        print("Numbered choices. Press Enter for defaults or q to cancel.")
        plan = make_plan()
        print("\nReview")
        print("  Mode: " + plan.mode)
        print("  Microphone: " + (
            "Android phone" if plan.source_kind == "android" else str(plan.input_device)
        ))
        print("  Speaker: " + str(plan.output_device))
        print("  OpenClaw: " + (
            plan.openclaw_setup if plan.install_openclaw else "skip"
        ))
        print("  Owner: " + plan.owner_name)
        print("  Start on boot: " + ("yes" if plan.start_at_boot else "no"))
        if not _yes_no("Apply this configuration?", default=False):
            print("No changes made.")
            return 0

        # Import after prompting, so an unusable terminal never changes host state.
        from .install_engine import run_install
        outcome = None
        try:
            outcome = run_install(plan, _launcher(), _progress)
        finally:
            plan.passphrase = ""

        print("\nJervis core installation complete.")
        for warning in outcome.warnings:
            print("Warning: " + warning)
        if outcome.openclaw_cli and outcome.openclaw_needs_wizard:
            print("\nStarting OpenClaw's own guided setup.")
            print("You can rerun it later using 'openclaw onboard'.")
            from .openclaw_setup import run as run_openclaw
            try:
                result = run_openclaw(
                    Path(outcome.openclaw_cli), "onboard", interactive=True
                )
                if result.returncode != 0:
                    print("OpenClaw onboarding incomplete. Run 'openclaw onboard' later.")
                else:
                    print("OpenClaw onboarding completed.")
            except (KeyboardInterrupt, OSError, subprocess.TimeoutExpired) as exc:
                print("OpenClaw onboarding interrupted: " + str(exc))
                print("Jervis remains installed. Run 'openclaw onboard' later.")
        print("Next: jervis status, jervis doctor, or jervis run")
        return 0
    except (Cancelled, KeyboardInterrupt, EOFError):
        print("\nSetup cancelled.")
        return 130
    except (RuntimeError, ValueError, OSError) as exc:
        print("Setup stopped: " + str(exc), file=sys.stderr)
        return 1


def home() -> int:
    """No fullscreen interface; never consume piped stdin or mutate state on no-TTY."""
    print(f"\nJervis {__version__}")
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print("Commands: jervis status | doctor | install | run | repair-center")
        print("Use 'jervis --help' for all options.")
        return 0

    actions = [
        ("Show system status", ["status"]),
        ("Set up or reconfigure", ["install"]),
        ("Start voice assistant", ["run"]),
        ("Run health checks", ["doctor"]),
        ("Check for updates", ["update-check"]),
        ("Show recovery options", ["repair-center"]),
        ("Show command help", ["--help"]),
        ("Exit", None),
    ]
    while True:
        try:
            picked = _choice(
                "What would you like to do?",
                [(label, str(index)) for index, (label, _) in enumerate(actions)],
                1,
            )
            command = actions[int(picked)][1]
            if command is None:
                return 0
            from .cli import main

            try:
                main(command)
            except SystemExit as exc:
                if exc.code not in (None, 0):
                    print("Command exited with status " + str(exc.code))
        except (Cancelled, KeyboardInterrupt, EOFError):
            print("\nGoodbye.")
            return 0


def installer_entry() -> None:
    raise SystemExit(install())
