from __future__ import annotations

import json
import secrets
import subprocess
from pathlib import Path
from typing import Callable

from .config import DEFAULT_CONFIG, load, save
from .install_plan import InstallOutcome, InstallPlan
from .install_tx import InstallTransaction
from .openclaw_setup import doctor as openclaw_doctor
from .openclaw_setup import find_openclaw, install_official
from .paths import Paths
from .platforms import current_platform
from .prereqs import ensure_adb, ensure_linux_audio, ensure_linux_openclaw_tools
from .security import hash_passphrase
from .speaker_model import ensure_speaker_model
from .state import State

Progress = Callable[[int, int, str, str], None]
TOTAL_STEPS = 8


def _emit(callback: Progress, step: int, title: str, detail: str = "") -> None:
    callback(step, TOTAL_STEPS, title, detail)


def _android_devices(adb: Path) -> list[str]:
    proc = subprocess.run(
        [str(adb), "devices"],
        text=True,
        capture_output=True,
        check=True,
    )
    return [
        line.split("\t", 1)[0]
        for line in proc.stdout.splitlines()
        if line.endswith("\tdevice")
    ]


def _configure_owner(paths: Paths, config: dict, plan: InstallPlan) -> None:
    state = State(
        paths.data / "jervis.sqlite3",
        config["privacy"]["max_dialogue_rows"],
        config["privacy"]["max_event_rows"],
    )
    try:
        users = state.users()
        existing_hash = state.get_kv("auth.passphrase_hash")
        if users:
            owner = next(
                (user for user in users if str(user["role"]) == "owner"),
                users[0],
            )
            if not isinstance(existing_hash, str):
                state.set_kv("auth.passphrase_hash", hash_passphrase(plan.passphrase))
                state.set_kv("owner_user_id", str(owner["id"]))
            return

        user_id = secrets.token_hex(8)
        state.upsert_user(
            user_id,
            plan.owner_name.strip(),
            plan.honorific,
            "owner",
        )
        state.set_kv("auth.passphrase_hash", hash_passphrase(plan.passphrase))
        state.set_kv("owner_user_id", user_id)
    finally:
        state.close()


def _reconcile_startup(
    adapter,
    transaction: InstallTransaction,
    launcher: Path,
    env: dict[str, str],
    new_mode: str,
    start_at_boot: bool,
    previous_mode: str,
) -> None:
    installed = bool(adapter.service_installed())

    def restore_previous() -> None:
        adapter.install_service(launcher, env, mode=previous_mode)

    if start_at_boot:
        if installed:
            transaction.mark_service_changed(restore_previous)
            adapter.remove_service()
        else:
            transaction.mark_service_changed()
        adapter.install_service(launcher, env, mode=new_mode)
        return

    if installed:
        transaction.mark_service_changed(restore_previous)
        adapter.remove_service()


def run_install(
    plan: InstallPlan,
    launcher: Path,
    progress: Progress,
) -> InstallOutcome:
    plan.validate()
    outcome = InstallOutcome()

    _emit(progress, 1, "Checking this system", "Validating audio and OS prerequisites")
    ensure_linux_audio(lambda _message: True)

    _emit(progress, 2, "Preparing OpenClaw", "Reusing an existing install when possible")
    cli = find_openclaw()
    if cli is None and plan.install_openclaw:
        ensure_linux_openclaw_tools()
        cli = install_official(
            lambda message: _emit(progress, 2, "Preparing OpenClaw", message)
        )
    if cli is None:
        outcome.warnings.append("OpenClaw is not configured; local Jervis features remain available.")
    else:
        outcome.openclaw_cli = str(cli)

    _emit(progress, 3, "Resolving audio", "Checking selected microphone and output")
    android_serial = plan.android_serial
    if plan.source_kind == "android":
        adb = ensure_adb(lambda _message: True)
        serials = _android_devices(adb)
        if android_serial and android_serial not in serials:
            raise RuntimeError("The selected Android phone is no longer connected over ADB.")
        if not android_serial:
            if len(serials) == 1:
                android_serial = serials[0]
            elif not serials:
                raise RuntimeError(
                    "No authorized Android phone is connected. Enable USB debugging and reconnect it."
                )
            else:
                raise RuntimeError(
                    "More than one Android phone is connected. Go back and choose a specific device."
                )

    _emit(progress, 4, "Voice recognition", "Verifying the local speaker-recognition model")
    paths = Paths.resolve()
    paths.ensure()
    model_ok = ensure_speaker_model(
        paths.data / "models" / "speaker.onnx",
        lambda message: _emit(progress, 4, "Voice recognition", message),
    )
    if not model_ok:
        outcome.warnings.append(
            "The speaker model could not be downloaded; trusted sessions still work after explicit auth."
        )

    _emit(progress, 5, "Writing configuration", "Applying your Desktop/Server and audio choices")
    config_path = paths.config / "config.json"
    database_path = paths.data / "jervis.sqlite3"
    if config_path.exists():
        config = load(config_path)
    else:
        config = json.loads(json.dumps(DEFAULT_CONFIG))

    previous_mode = str(config["install"].get("mode", "desktop"))

    config["install"]["mode"] = plan.mode
    config["install"]["start_at_boot"] = bool(plan.start_at_boot)
    config["audio"]["source"] = {
        "kind": plan.source_kind,
        "device": plan.input_device if plan.source_kind == "desktop" else None,
        "android_serial": android_serial if plan.source_kind == "android" else None,
    }
    config["audio"]["output_device"] = plan.output_device

    adapter = current_platform()
    with InstallTransaction(adapter) as transaction:
        transaction.track_file(config_path)
        transaction.track_file(database_path)
        transaction.track_file(Path(str(database_path) + "-wal"))
        transaction.track_file(Path(str(database_path) + "-shm"))

        save(config_path, config)
        load(config_path)

        _emit(progress, 6, "Creating your profile", "Securing the owner account locally")
        _configure_owner(paths, config, plan)

        _emit(progress, 7, "Startup integration", "Connecting Jervis to the operating system")
        service_env = {
            "JERVIS_HOME": str(paths.root),
            "JERVIS_LOG_HOME": str(paths.logs),
        }
        _reconcile_startup(
            adapter,
            transaction,
            launcher,
            service_env,
            plan.mode,
            bool(plan.start_at_boot),
            previous_mode,
        )

        _emit(progress, 8, "Final checks", "Verifying configuration and OpenClaw health")
        load(config_path)
        if cli:
            healthy, _detail = openclaw_doctor(cli)
            if not healthy:
                outcome.warnings.append(
                    "OpenClaw doctor reported warnings; finish sign-in and run openclaw doctor."
                )

        transaction.commit()

    return outcome
