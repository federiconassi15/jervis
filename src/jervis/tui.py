from __future__ import annotations

import curses
import secrets
import time

from .agents import openclaw_agents
from .config import load, save
from .openclaw_setup import find_openclaw
from .paths import Paths
from .repair import repair
from .snapshots import create_snapshot, list_snapshots
from .status import collect_status
from .permissions import describe_role
from .security import verify_passphrase
from .skills import SkillManager
from .state import State
from .version import __version__

TABS = [
    "DASH",
    "DIALOGUE",
    "PEOPLE",
    "AUDIO",
    "BRAIN",
    "SKILLS",
    "AGENTS",
    "MEMORY",
    "PERMISSIONS",
    "TIMELINE",
    "LOGS",
    "RECOVERY",
    "SETTINGS",
    "AUTH",
]


def safe(screen, y: int, x: int, text: str, attr: int = 0) -> None:
    height, width = screen.getmaxyx()
    if 0 <= y < height and 0 <= x < width:
        try:
            screen.addnstr(y, x, text, max(0, width - x - 1), attr)
        except curses.error:
            pass


def prompt(screen, label: str, secret: bool = False) -> str:
    height, width = screen.getmaxyx()
    y = max(0, height - 2)
    screen.nodelay(False)
    curses.curs_set(1)
    if secret:
        curses.noecho()
    else:
        curses.echo()
    try:
        safe(screen, y, 2, " " * max(0, width - 4))
        safe(screen, y, 2, label)
        screen.refresh()
        raw = screen.getstr(y, min(width - 2, 2 + len(label)), max(1, width - len(label) - 5))
        return raw.decode("utf-8", "replace").strip()
    finally:
        curses.noecho()
        curses.curs_set(0)
        screen.nodelay(True)


def auth_action(screen, state: State) -> str:
    users = state.users()
    choices = [str(index + 1) + ". " + str(user["name"]) for index, user in enumerate(users)]
    choices.append("N. New person")

    screen.erase()
    safe(screen, 0, 2, "JERVIS AUTHENTICATION", curses.A_BOLD)
    for index, choice in enumerate(choices[:20]):
        safe(screen, 2 + index, 2, choice)
    screen.refresh()

    selected = prompt(screen, "Select identity: ")
    new_person = selected.lower() == "n"
    user = None
    if not new_person:
        if not selected.isdigit() or not 1 <= int(selected) <= len(users):
            return "Invalid identity selection."
        user = users[int(selected) - 1]

    encoded = state.get_kv("auth.passphrase_hash")
    if not isinstance(encoded, str):
        return "No authentication passphrase is configured."

    password = prompt(screen, "Password: ", secret=True)
    if not verify_passphrase(password, encoded):
        state.event("tui_auth_failed", "invalid passphrase")
        return "Authentication failed."

    if new_person:
        name = prompt(screen, "Name: ")
        if not name:
            return "Name cannot be empty."
        existing = state.user_by_name(name)
        if existing is not None:
            user = existing
        else:
            user_id = secrets.token_hex(8)
            state.upsert_user(user_id, name, None, "known")
            user = state.user(user_id)

    if user is None:
        return "Authentication failed."

    state.set_kv(
        "auth.tui_grant",
        {
            "user_id": str(user["id"]),
            "issued_at": time.time(),
        },
    )
    state.event("tui_auth_granted", "user=" + str(user["id"]))
    return "Authenticated as " + str(user["name"]) + "."


def run() -> None:
    paths = Paths.resolve()
    paths.ensure()
    state = State(paths.data / "jervis.sqlite3")
    config_path = paths.config / "config.json"

    skills = SkillManager([paths.data / "skills", paths.root / "skills"])
    skill_cache = skills.discover()
    agent_cache = openclaw_agents()
    openclaw_path = find_openclaw()

    def app(screen) -> None:
        curses.curs_set(0)
        screen.nodelay(True)
        tab = 0
        notice = ""
        recovery_cache = None
        recovery_cache_at = 0.0

        while True:
            screen.erase()
            safe(screen, 0, 2, "JERVIS CONTROL DECK  v" + __version__, curses.A_BOLD)
            safe(
                screen,
                1,
                2,
                "  ".join(
                    ("[" + name + "]" if index == tab else name)
                    for index, name in enumerate(TABS)
                ),
            )
            active = str(state.get_kv("activity", "Idle — waiting for Jervis"))
            safe(screen, 3, 2, "ACTIVE: " + active)
            name = TABS[tab]

            if name == "DASH":
                safe(screen, 5, 2, "←/→ navigate · q quit")
                safe(screen, 6, 2, "AUTH: press A from the AUTH tab")
                safe(screen, 7, 2, "AUDIO: +/- changes Jervis speech volume")
            elif name == "DIALOGUE":
                rows = state.recent_dialogue(20)
                for index, row in enumerate(rows):
                    stamp = time.strftime("%H:%M:%S", time.localtime(row["ts"]))
                    role = str(row["role"])
                    if role.lower() == "jervis":
                        label = "Jervis:"
                    elif role.lower() == "unknown":
                        label = "Unknown:"
                    else:
                        label = "[" + role + "]:"
                    safe(
                        screen,
                        5 + index,
                        2,
                        stamp + "  " + label + " " + str(row["text"]),
                    )
            elif name == "PEOPLE":
                for index, user in enumerate(state.users()[:20]):
                    safe(
                        screen,
                        5 + index,
                        2,
                        str(user["name"])
                        + "  role="
                        + str(user["role"])
                        + "  address="
                        + str(user["honorific"] or "not set"),
                    )
            elif name == "AUDIO":
                try:
                    config = load(config_path)
                    volume = float(
                        state.get_kv(
                            "audio.jervis_volume",
                            config["audio"]["jervis_volume"],
                        )
                    )
                    source = config["audio"]["source"]
                    safe(screen, 5, 2, "Jervis volume: " + str(round(volume * 100)) + "%")
                    safe(screen, 6, 2, "Use + / - to adjust from 5% to 200%.")
                    safe(screen, 8, 2, "Input: " + str(source))
                    safe(
                        screen,
                        9,
                        2,
                        "Output device: " + str(config["audio"]["output_device"]),
                    )
                    quality = state.get_kv("audio.last_quality")
                    if isinstance(quality, dict):
                        safe(
                            screen,
                            11,
                            2,
                            "Last input: "
                            + str(quality.get("label", "unknown"))
                            + " · score="
                            + format(float(quality.get("score", 0.0)), ".2f")
                            + " · rms="
                            + format(float(quality.get("rms", 0.0)), ".4f")
                            + " · clipping="
                            + format(float(quality.get("clipping", 0.0)) * 100.0, ".2f")
                            + "%",
                        )
                except Exception as exc:
                    safe(screen, 5, 2, "Audio config error: " + str(exc))
            elif name == "BRAIN":
                try:
                    config = load(config_path)
                    safe(screen, 5, 2, "Provider: " + str(config["brain"]["provider"]))
                    safe(screen, 6, 2, "Agent: " + str(config["brain"]["agent"]))
                    safe(screen, 7, 2, "Thinking: " + str(config["brain"]["thinking"]))
                    safe(screen, 8, 2, "OpenClaw: " + (str(openclaw_path) if openclaw_path else "not found"))
                    safe(screen, 9, 2, "Last route: " + str(state.get_kv("brain.last_route", "none yet")))
                except Exception as exc:
                    safe(screen, 5, 2, "Brain config error: " + str(exc))
            elif name == "SKILLS":
                if not skill_cache:
                    safe(screen, 5, 2, "No user skills discovered.")
                    safe(screen, 6, 2, "Install skills under the Jervis data skills directory.")
                for index, skill in enumerate(list(skill_cache.values())[:18]):
                    detail = skill.name + "  permission=" + skill.permission.value
                    if skill.description:
                        detail += "  " + skill.description
                    safe(screen, 5 + index, 2, detail)
            elif name == "AGENTS":
                if not agent_cache:
                    safe(screen, 5, 2, "No OpenClaw agents reported.")
                for index, agent in enumerate(agent_cache[:18]):
                    label = str(
                        agent.get("name")
                        or agent.get("id")
                        or agent.get("agent")
                        or "unnamed"
                    )
                    safe(screen, 5 + index, 2, label)
            elif name == "MEMORY":
                row = 5
                for user in state.users():
                    memories = state.memories(str(user["id"]), 6)
                    if not memories:
                        continue
                    safe(screen, row, 2, str(user["name"]) + ":", curses.A_BOLD)
                    row += 1
                    for item in memories:
                        safe(
                            screen,
                            row,
                            4,
                            str(item["key"]) + " = " + str(item["value"]),
                        )
                        row += 1
                        if row >= screen.getmaxyx()[0] - 3:
                            break
                    if row >= screen.getmaxyx()[0] - 3:
                        break
                if row == 5:
                    safe(screen, 5, 2, "No explicit per-user memories saved yet.")
            elif name == "PERMISSIONS":
                for index, user in enumerate(state.users()[:18]):
                    safe(
                        screen,
                        5 + index,
                        2,
                        str(user["name"])
                        + "  role="
                        + str(user["role"])
                        + "  grants="
                        + describe_role(str(user["role"])),
                    )
            elif name == "TIMELINE":
                rows = state.recent_events(20)
                for index, row in enumerate(rows):
                    stamp = time.strftime("%H:%M:%S", time.localtime(row["ts"]))
                    safe(
                        screen,
                        5 + index,
                        2,
                        stamp + "  " + str(row["kind"]) + ": " + str(row["detail"]),
                    )
            elif name == "LOGS":
                rows = state.recent_events(20)
                for index, row in enumerate(rows):
                    stamp = time.strftime("%H:%M:%S", time.localtime(row["ts"]))
                    safe(
                        screen,
                        5 + index,
                        2,
                        stamp + "  " + str(row["kind"]) + "  " + str(row["detail"]),
                    )
                if not rows:
                    safe(screen, 5, 2, "No runtime events recorded yet.")
            elif name == "RECOVERY":
                try:
                    if recovery_cache is None or time.time() - recovery_cache_at >= 2.0:
                        recovery_cache = collect_status(paths)
                        recovery_cache_at = time.time()
                    report = recovery_cache
                    safe(screen, 5, 2, "RECOVERY CENTER", curses.A_BOLD)
                    safe(
                        screen,
                        6,
                        2,
                        "Service: "
                        + ("OK" if report["service"]["ok"] else "ATTENTION")
                        + " · "
                        + str(report["service"]["detail"]),
                    )
                    safe(
                        screen,
                        7,
                        2,
                        "OpenClaw: "
                        + ("OK" if report["openclaw"]["ok"] else "ATTENTION")
                        + " · "
                        + str(report["openclaw"]["detail"]),
                    )
                    safe(
                        screen,
                        8,
                        2,
                        "Recovery: "
                        + (
                            "previous run unclean"
                            if report["crash"]["previous_unclean"]
                            else "clean"
                        ),
                    )
                    snapshots = list_snapshots(paths=paths)
                    safe(screen, 9, 2, "Snapshots: " + str(len(snapshots)))
                    if snapshots:
                        safe(screen, 10, 2, "Latest: " + snapshots[0].id)
                    safe(screen, 12, 2, "R = repair all · S = create snapshot")
                    safe(screen, 13, 2, "CLI: jervis snapshot restore <id> for rollback")
                except Exception as exc:
                    safe(screen, 5, 2, "Recovery center error: " + str(exc))
            elif name == "SETTINGS":
                try:
                    config = load(config_path)
                    safe(screen, 5, 2, "Mode: " + str(config["install"]["mode"]))
                    safe(screen, 6, 2, "Start at boot: " + str(config["install"]["start_at_boot"]))
                    safe(screen, 7, 2, "Wake word: " + str(config["assistant"]["wake_word"]))
                    safe(screen, 8, 2, "Follow-up window: " + str(config["speech"]["follow_up_seconds"]) + "s")
                    safe(screen, 9, 2, "Presence timeout: " + str(config["presence"]["timeout_seconds"]) + "s")
                    safe(
                        screen,
                        10,
                        2,
                        "Quiet hours: "
                        + str(config["proactive"]["quiet_hours_start"])
                        + "–"
                        + str(config["proactive"]["quiet_hours_end"]),
                    )
                    safe(screen, 11, 2, "Persist dialogue: " + str(config["privacy"]["persist_dialogue"]))
                except Exception as exc:
                    safe(screen, 5, 2, "Settings error: " + str(exc))
            elif name == "AUTH":
                safe(screen, 5, 2, "Press A to authenticate.")
                safe(
                    screen,
                    6,
                    2,
                    "Select your identity, then enter the Jervis passphrase.",
                )
                safe(
                    screen,
                    7,
                    2,
                    "The password is verified locally and is never added to dialogue.",
                )
            else:
                safe(screen, 5, 2, "No panel renderer is registered for " + name + ".")

            if notice:
                height, _ = screen.getmaxyx()
                safe(screen, max(0, height - 4), 2, notice, curses.A_BOLD)

            screen.refresh()
            key = screen.getch()
            if key in (ord("q"), 27):
                break
            if key == curses.KEY_RIGHT:
                tab = (tab + 1) % len(TABS)
                notice = ""
            elif key == curses.KEY_LEFT:
                tab = (tab - 1) % len(TABS)
                notice = ""
            elif name == "AUTH" and key in (ord("a"), ord("A")):
                notice = auth_action(screen, state)
            elif name == "RECOVERY" and key in (ord("s"), ord("S")):
                try:
                    snap = create_snapshot("control-deck-manual", paths=paths)
                    recovery_cache = None
                    notice = "Snapshot created: " + snap.id
                except Exception as exc:
                    notice = "Snapshot failed: " + str(exc)
            elif name == "RECOVERY" and key in (ord("r"), ord("R")):
                try:
                    results = repair("all", paths=paths)
                    recovery_cache = None
                    failed = [item.component for item in results if not item.ok]
                    notice = (
                        "Repair complete."
                        if not failed
                        else "Repair needs attention: " + ", ".join(failed)
                    )
                except Exception as exc:
                    notice = "Repair failed: " + str(exc)
            elif name == "AUDIO" and key in (ord("+"), ord("="), ord("-"), ord("_")):
                try:
                    config = load(config_path)
                    current = float(
                        state.get_kv(
                            "audio.jervis_volume",
                            config["audio"]["jervis_volume"],
                        )
                    )
                    delta = 0.1 if key in (ord("+"), ord("=")) else -0.1
                    volume = max(0.05, min(2.0, round(current + delta, 2)))
                    config["audio"]["jervis_volume"] = volume
                    save(config_path, config)
                    state.set_kv("audio.jervis_volume", volume)
                    state.event("jervis_volume_changed", str(volume))
                    notice = "Jervis volume " + str(round(volume * 100)) + "%"
                except Exception as exc:
                    notice = "Volume change failed: " + str(exc)

            time.sleep(0.05)

    try:
        curses.wrapper(app)
    finally:
        state.close()
