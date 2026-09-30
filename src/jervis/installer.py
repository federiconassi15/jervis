from __future__ import annotations

import getpass
import json
import os
import platform
import random
import secrets
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

from .audio.devices import default_devices, list_devices
from .config import DEFAULT_CONFIG, load, save
from .install_tx import InstallTransaction
from .openclaw_setup import configure as configure_openclaw
from .openclaw_setup import doctor as openclaw_doctor
from .openclaw_setup import find_openclaw, install_official
from .paths import Paths
from .platforms import current_platform
from .prereqs import ensure_adb, ensure_linux_audio
from .security import hash_passphrase
from .state import State

BLUE = "\033[38;5;45m"
DIM = "\033[2m"
RESET = "\033[0m"
GREEN = "\033[38;5;82m"
YELLOW = "\033[38;5;220m"
RED = "\033[31m"

BANTER = [
    "Jervis, make me like Tony Stank.",
    "Teaching your computer manners.",
    "No arc reactor required.",
    "Deploying questionable amounts of intelligence.",
    "Please do not unplug reality.",
    "One moment, boss.",
    "Installing good decisions. Results may vary.",
    "Turning caffeine into automation.",
]


def color(text: str, value: str) -> str:
    return value + text + RESET if sys.stdout.isatty() else text


def header() -> None:
    print(color("╭──────────────────────────────────────────────╮", BLUE))
    print(color("│                J E R V I S                   │", BLUE))
    print(color("│         intelligent systems installer        │", BLUE))
    print(color("╰──────────────────────────────────────────────╯", BLUE))
    print()
    print(color("  “" + random.choice(BANTER) + "”", DIM))
    print()


def choose(prompt: str, options: list[str], default: int = 0) -> int:
    print(prompt)
    for index, option in enumerate(options):
        print("  " + ("›" if index == default else " ") + " " + str(index + 1) + ". " + option)
    while True:
        value = input("Choose [" + str(default + 1) + "]: ").strip()
        if not value:
            return default
        if value.isdigit() and 1 <= int(value) <= len(options):
            return int(value) - 1
        print("Enter one of the listed numbers.")


def yes_no(prompt: str, default: bool = True) -> bool:
    suffix = " [Y/n]: " if default else " [y/N]: "
    value = input(prompt + suffix).strip().lower()
    if not value:
        return default
    return value in {"y", "yes"}


def progress(text: str) -> None:
    print(color("  • " + text, BLUE))


def setup_openclaw(mode: str) -> Path | None:
    cli = find_openclaw()
    if cli:
        print(color("  ✓ OpenClaw detected", GREEN))
        healthy, _ = openclaw_doctor(cli)
        if healthy:
            return cli
        if yes_no("OpenClaw exists but needs configuration. Configure it now?"):
            configure_openclaw(cli, mode, choose)
        return cli

    if not yes_no("OpenClaw is required for Jervis's agentic brain. Install it now?"):
        print(color("  ! OpenClaw skipped; local Jervis features will still install.", YELLOW))
        return None

    cli = install_official(progress)
    print(color("  ✓ OpenClaw installed", GREEN))
    configure_openclaw(cli, mode, choose)
    return cli


def audio_test(input_device: int | None, output_device: int, sample_rate: int) -> None:
    import sounddevice as sd

    if yes_no("Play a short speaker test tone?"):
        seconds = 0.25
        timeline = np.arange(int(sample_rate * seconds), dtype=np.float32) / sample_rate
        tone = (0.12 * np.sin(2 * np.pi * 440 * timeline)).astype(np.float32)
        sd.play(tone, samplerate=sample_rate, device=output_device)
        sd.wait()

    if input_device is not None and yes_no("Test the selected microphone for half a second?"):
        recording = sd.rec(
            int(sample_rate * 0.5),
            samplerate=sample_rate,
            channels=1,
            dtype="float32",
            device=input_device,
        )
        sd.wait()
        level = float(np.sqrt(np.mean(np.square(recording), dtype=np.float64)))
        shade = GREEN if level > 0.002 else YELLOW
        print(color("  ✓ Microphone RMS " + format(level, ".4f"), shade))


def pick_audio(config: dict) -> None:
    ensure_linux_audio(yes_no)
    devices = list_devices()
    inputs = [device for device in devices if device.inputs > 0]
    outputs = [device for device in devices if device.outputs > 0]
    default_input, default_output = default_devices()

    source_choice = choose("Microphone source", ["Computer microphone", "Android phone over ADB"])
    selected_input: int | None = None

    if source_choice == 1:
        adb = ensure_adb(yes_no)
        proc = subprocess.run([str(adb), "devices"], text=True, capture_output=True, check=True)
        serials = [
            line.split("\t", 1)[0]
            for line in proc.stdout.splitlines()
            if line.endswith("\tdevice")
        ]
        if not serials:
            raise RuntimeError("no authorized Android device is visible to ADB")
        serial = serials[choose("Android device", serials)]
        config["audio"]["source"] = {
            "kind": "android",
            "device": None,
            "android_serial": serial,
        }
    else:
        if not inputs:
            raise RuntimeError("no microphone devices detected")
        default = next(
            (index for index, device in enumerate(inputs) if device.index == default_input),
            0,
        )
        device = inputs[
            choose(
                "Microphone",
                [item.name + " (" + item.hostapi + ")" for item in inputs],
                default,
            )
        ]
        selected_input = device.index
        config["audio"]["source"] = {
            "kind": "desktop",
            "device": selected_input,
            "android_serial": None,
        }

    if not outputs:
        raise RuntimeError("no speaker/output devices detected")
    default = next(
        (index for index, device in enumerate(outputs) if device.index == default_output),
        0,
    )
    output = outputs[
        choose(
            "Output",
            [item.name + " (" + item.hostapi + ")" for item in outputs],
            default,
        )
    ]
    config["audio"]["output_device"] = output.index
    audio_test(selected_input, output.index, int(config["audio"]["sample_rate"]))


def setup_owner(paths: Paths, config: dict) -> None:
    state = State(
        paths.data / "jervis.sqlite3",
        config["privacy"]["max_dialogue_rows"],
        config["privacy"]["max_event_rows"],
    )
    try:
        if state.users():
            return
        print()
        print(color("First user", BLUE))
        name = input("Your name: ").strip()
        if not name:
            raise RuntimeError("owner name cannot be empty")
        honorific = ["sir", "maam"][choose("How should Jervis address you?", ["Sir", "Ma'am"])]

        while True:
            first = getpass.getpass("Create the Jervis authentication passphrase: ")
            second = getpass.getpass("Confirm passphrase: ")
            if first != second:
                print("Passphrases do not match.")
                continue
            if len(first) < 8:
                print("Use at least 8 characters.")
                continue
            break

        user_id = secrets.token_hex(8)
        state.upsert_user(user_id, name, honorific, "owner")
        state.set_kv("auth.passphrase_hash", hash_passphrase(first))
        state.set_kv("owner_user_id", user_id)
    finally:
        state.close()


def resolve_launcher() -> Path:
    override = os.environ.get("JERVIS_LAUNCHER_PATH")
    if override:
        return Path(override)
    found = shutil.which("jervis")
    if found:
        return Path(found)
    candidate = Path(sys.executable).with_name("jervis.exe" if os.name == "nt" else "jervis")
    if candidate.exists():
        return candidate
    raise RuntimeError("could not locate the Jervis launcher")


def install() -> None:
    header()
    system = platform.system()
    if system not in {"Linux", "Darwin", "Windows"}:
        raise RuntimeError("unsupported operating system: " + system)

    print(color("  ✓ " + system + " " + platform.release() + " detected", GREEN))
    print(color("  ✓ " + platform.machine() + " architecture", GREEN))
    print(color("  ✓ Python " + platform.python_version(), GREEN))
    print()

    mode = ["desktop", "server"][choose("Installation type", ["Desktop", "Server"])]
    cli = setup_openclaw(mode)

    config = json.loads(json.dumps(DEFAULT_CONFIG))
    config["install"]["mode"] = mode
    config["install"]["start_at_boot"] = (
        True if mode == "server" else yes_no("Start Jervis automatically when you sign in?")
    )
    pick_audio(config)

    paths = Paths.resolve()
    paths.ensure()
    config_path = paths.config / "config.json"
    database_path = paths.data / "jervis.sqlite3"
    adapter = current_platform()

    with InstallTransaction(adapter) as transaction:
        transaction.track_file(config_path)
        transaction.track_file(database_path)
        transaction.track_file(Path(str(database_path) + "-wal"))
        transaction.track_file(Path(str(database_path) + "-shm"))

        save(config_path, config)
        load(config_path)
        setup_owner(paths, config)

        if config["install"]["start_at_boot"]:
            existing_service = False
            try:
                existing_service = bool(adapter.service_health().ok)
            except Exception:
                pass
            if not existing_service:
                adapter.install_service(resolve_launcher(), paths.service_environment(), mode=mode)
                transaction.mark_service_changed()

        transaction.commit()

    print()
    print(color("  ✓ Jervis configuration verified", GREEN))
    if config["install"]["start_at_boot"]:
        print(color("  ✓ Startup integration configured", GREEN))
    if cli:
        healthy, detail = openclaw_doctor(cli)
        if healthy:
            print(color("  ✓ OpenClaw doctor passed", GREEN))
        else:
            print(color("  ! OpenClaw doctor reported warnings", YELLOW))
            if detail:
                print(color("    Run openclaw doctor for details.", DIM))
    print()
    print(color("Jervis setup is complete.", BLUE))
    print("Run jervis doctor to verify the full installation.")


def main() -> None:
    try:
        install()
    except KeyboardInterrupt:
        print("\nInstallation cancelled.")
        raise SystemExit(130)
    except Exception as exc:
        print(color("\nInstallation failed: " + str(exc), RED))
        raise SystemExit(1)
