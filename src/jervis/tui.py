from __future__ import annotations

import curses
import secrets
import time

from .agents import agent_capabilities, openclaw_agents
from .benchmark import load_benchmark_history
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
    "PERF",
    "DIALOGUE",
    "PEOPLE",
    "AUDIO",
    "BRAIN",
    "SKILLS",
    "AGENTS",
    "MEMORY",
    "PROACTIVE",
    "PERMISSIONS",
    "TIMELINE",
    "LOGS",
    "RECOVERY",
    "SETTINGS",
    "AUTH",
]


_BODY_X = 2


def raw_safe(screen, y: int, x: int, text: str, attr: int = 0) -> None:
    height, width = screen.getmaxyx()
    if 0 <= y < height and 0 <= x < width:
        try:
            screen.addnstr(y, x, text, max(0, width - x - 1), attr)
        except curses.error:
            pass


def safe(screen, y: int, x: int, text: str, attr: int = 0) -> None:
    actual_x = (_BODY_X + x - 2) if _BODY_X != 2 and x >= 2 else x
    raw_safe(screen, y, actual_x, text, attr)


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
        start = _BODY_X
        safe(screen, y, 2, " " * max(0, width - start - 2))
        safe(screen, y, 2, label)
        screen.refresh()
        cursor_x = min(width - 2, start + len(label))
        raw = screen.getstr(
            y,
            cursor_x,
            max(1, width - cursor_x - 2),
        )
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


def _pick_user(screen, state: State):
    users = state.users()
    if not users:
        return None
    selected = prompt(
        screen,
        "User (number or name): ",
    )
    if selected.isdigit() and 1 <= int(selected) <= len(users):
        return users[int(selected) - 1]
    return state.user_by_name(selected)


def memory_edit_action(screen, state: State) -> str:
    users = state.users()
    if not users:
        return "No users exist yet."
    screen.erase()
    safe(screen, 0, 2, "EDIT MEMORY", curses.A_BOLD)
    for index, user in enumerate(users[:16], start=1):
        safe(screen, 1 + index, 2, str(index) + ". " + str(user["name"]))
    user = _pick_user(screen, state)
    if user is None:
        return "User not found."
    key = prompt(screen, "Memory key: ")
    if not key:
        return "Memory key cannot be empty."
    value = prompt(screen, "Memory value: ")
    if not value:
        return "Memory value cannot be empty."
    state.remember(
        str(user["id"]),
        key,
        value,
        provenance="control-deck:explicit",
        importance=0.8,
    )
    state.event(
        "memory_edited",
        "user=" + str(user["id"]) + " key=" + key,
    )
    return "Memory saved."


def memory_delete_action(screen, state: State) -> str:
    users = state.users()
    if not users:
        return "No users exist yet."
    screen.erase()
    safe(screen, 0, 2, "DELETE MEMORY", curses.A_BOLD)
    for index, user in enumerate(users[:16], start=1):
        safe(screen, 1 + index, 2, str(index) + ". " + str(user["name"]))
    user = _pick_user(screen, state)
    if user is None:
        return "User not found."
    key = prompt(screen, "Memory key to delete: ")
    if not key:
        return "No memory key entered."
    state.forget_memory(str(user["id"]), key)
    state.event(
        "memory_deleted",
        "user=" + str(user["id"]) + " key=" + key,
    )
    return "Memory deleted."


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
            global _BODY_X
            screen.erase()
            height, width = screen.getmaxyx()
            sidebar = width >= 90
            _BODY_X = 26 if sidebar else 2

            name = TABS[tab]
            if sidebar:
                raw_safe(screen, 0, 2, "JERVIS", curses.A_BOLD)
                raw_safe(screen, 1, 2, "CONTROL DECK  v" + __version__)
                raw_safe(screen, 2, 2, "────────────────────")
                for index, label in enumerate(TABS):
                    marker = "▸ " if index == tab else "  "
                    attr = curses.A_BOLD if index == tab else 0
                    raw_safe(screen, 3 + index, 2, marker + label, attr)
                raw_safe(
                    screen,
                    max(0, height - 3),
                    2,
                    "↑↓ panels",
                )
                raw_safe(
                    screen,
                    max(0, height - 2),
                    2,
                    "q quit",
                )
                safe(screen, 0, 2, name, curses.A_BOLD)
            else:
                safe(screen, 0, 2, "JERVIS CONTROL DECK  v" + __version__, curses.A_BOLD)
                safe(screen, 1, 2, "PANEL: " + name + "  ·  ←/→ switch")

            active = str(state.get_kv("activity", "Idle — waiting for Jervis"))
            safe(screen, 3, 2, "ACTIVE: " + active)

            if name == "DASH":
                try:
                    if recovery_cache is None or time.time() - recovery_cache_at >= 2.0:
                        recovery_cache = collect_status(paths)
                        recovery_cache_at = time.time()
                    report = recovery_cache
                    safe(
                        screen,
                        5,
                        2,
                        "SERVICE   "
                        + ("OK" if report["service"]["ok"] else "ATTENTION")
                        + "  ·  "
                        + str(report["service"]["detail"]),
                    )
                    safe(
                        screen,
                        6,
                        2,
                        "OPENCLAW  "
                        + ("OK" if report["openclaw"]["ok"] else "ATTENTION")
                        + "  ·  "
                        + str(report["openclaw"]["detail"]),
                    )
                    safe(
                        screen,
                        7,
                        2,
                        "ACCEL     "
                        + str(report["acceleration"]["backend"])
                        + (" native" if report["acceleration"]["native"] else " fallback"),
                    )
                    latency = report.get("latency_ms")
                    safe(
                        screen,
                        8,
                        2,
                        "LATENCY   "
                        + (
                            "no live median yet"
                            if latency is None
                            else format(float(latency), ".0f") + " ms median"
                        ),
                    )
                    safe(
                        screen,
                        10,
                        2,
                        "Use the sidebar to inspect memory, presence, agents, "
                        "proactive work, performance and recovery.",
                    )
                except Exception as exc:
                    safe(screen, 5, 2, "Dashboard error: " + str(exc))
            elif name == "PERF":
                rows = load_benchmark_history(paths=paths, limit=8)
                if not rows:
                    safe(screen, 5, 2, "No benchmark history yet.")
                    safe(screen, 6, 2, "Run: jervis benchmark")
                else:
                    safe(screen, 5, 2, "BENCHMARK HISTORY", curses.A_BOLD)
                    row_y = 7
                    for item in reversed(rows):
                        live = item.get("live", {})
                        stats = (
                            live.get("command_to_reply_ms")
                            if isinstance(live, dict)
                            else None
                        )
                        median = (
                            None
                            if not isinstance(stats, dict)
                            else stats.get("median")
                        )
                        stamp = time.strftime(
                            "%Y-%m-%d %H:%M",
                            time.localtime(float(item.get("timestamp", 0.0))),
                        )
                        safe(
                            screen,
                            row_y,
                            2,
                            stamp
                            + "  v"
                            + str(item.get("jervis_version", "?"))
                            + "  "
                            + (
                                "no live latency"
                                if median is None
                                else format(float(median), ".1f") + " ms median"
                            ),
                        )
                        row_y += 1
                        if row_y >= height - 2:
                            break
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
                active_user = state.get_kv("presence.active_user")
                presence_rows = {
                    str(row["user_id"]): row
                    for row in state.presence()
                }
                for index, user in enumerate(state.users()[:18]):
                    user_id = str(user["id"])
                    row = presence_rows.get(user_id)
                    marker = "▶ " if active_user == user_id else "  "
                    status = (
                        "present"
                        if row is not None and bool(row["present"])
                        else "away"
                    )
                    safe(
                        screen,
                        5 + index,
                        2,
                        marker
                        + str(user["name"])
                        + "  "
                        + status
                        + "  role="
                        + str(user["role"])
                        + "  via="
                        + (str(row["source"]) if row is not None else "—"),
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
                    safe(screen, 7 + index, 2, detail)
            elif name == "AGENTS":
                safe(
                    screen,
                    5,
                    2,
                    "C cancel latest running long task",
                    curses.A_BOLD,
                )
                safe(screen, 7, 2, "AVAILABLE", curses.A_BOLD)
                if not agent_cache:
                    safe(screen, 8, 2, "No OpenClaw agents reported.")
                for index, agent in enumerate(agent_cache[:5]):
                    meta = agent_capabilities(agent)
                    label = str(meta["name"] or "unnamed")
                    capabilities = ",".join(meta["capabilities"][:4]) or "unspecified"
                    safe(
                        screen,
                        8 + index,
                        2,
                        "• "
                        + label
                        + "  caps="
                        + capabilities
                        + "  upstream-cancel="
                        + ("yes" if meta["cancel_supported"] else "unknown/no"),
                    )

                row = 14
                safe(screen, row, 2, "RECENT RUNS", curses.A_BOLD)
                row += 1
                runs = state.recent_agent_runs(limit=6)
                for run in runs:
                    ended = "running" if run["ended_at"] is None else str(run["status"])
                    safe(
                        screen,
                        row,
                        2,
                        "#"
                        + str(run["id"])
                        + "  "
                        + str(run["agent"])
                        + "  "
                        + str(run["route"])
                        + "  "
                        + ended,
                    )
                    row += 1
                    if row >= height - 6:
                        break

                if runs and row < height - 3:
                    latest = runs[0]
                    actions = state.agent_actions(int(latest["id"]), 8)
                    safe(
                        screen,
                        row,
                        2,
                        "ACTIONS FOR #"
                        + str(latest["id"])
                        + (
                            "  (none exposed by OpenClaw)"
                            if not actions
                            else ""
                        ),
                        curses.A_BOLD,
                    )
                    row += 1
                    for action in actions:
                        safe(
                            screen,
                            row,
                            4,
                            str(action["kind"])
                            + "  "
                            + str(action["name"])
                            + (
                                "  " + str(action["status"])
                                if action["status"]
                                else ""
                            ),
                        )
                        row += 1
                        if row >= height - 2:
                            break
            elif name == "MEMORY":
                safe(screen, 5, 2, "E edit/add · D delete", curses.A_BOLD)
                row = 7
                for user in state.users():
                    user_id = str(user["id"])
                    memories = state.memories(user_id, 5)
                    summaries = state.recent_session_summaries(user_id, 2)
                    if not memories and not summaries:
                        continue
                    safe(screen, row, 2, str(user["name"]) + ":", curses.A_BOLD)
                    row += 1
                    for item in memories:
                        safe(
                            screen,
                            row,
                            4,
                            str(item["key"])
                            + " = "
                            + str(item["value"])
                            + "  ["
                            + str(item["provenance"])
                            + " / "
                            + format(float(item["importance"]), ".2f")
                            + "]",
                        )
                        row += 1
                        if row >= screen.getmaxyx()[0] - 5:
                            break
                    for item in summaries:
                        if row >= screen.getmaxyx()[0] - 3:
                            break
                        safe(
                            screen,
                            row,
                            4,
                            "↳ "
                            + (str(item["topic"]) + ": " if item["topic"] else "")
                            + str(item["summary"]),
                        )
                        row += 1
                    if row >= screen.getmaxyx()[0] - 3:
                        break
                if row == 7:
                    safe(screen, 7, 2, "No memories or continuity summaries yet.")
            elif name == "PROACTIVE":
                safe(
                    screen,
                    5,
                    2,
                    "X cancel item  ·  use n<ID> for notification or w<ID> for watch",
                    curses.A_BOLD,
                )
                row = 7
                watches = state.condition_watches(active_only=True, limit=6)
                safe(screen, row, 2, "CONDITION WATCHES", curses.A_BOLD)
                row += 1
                if not watches:
                    safe(screen, row, 4, "None")
                    row += 1
                else:
                    for item in watches:
                        safe(
                            screen,
                            row,
                            4,
                            "w"
                            + str(item["id"])
                            + "  "
                            + str(item["kind"])
                            + "  →  "
                            + str(item["message"]),
                        )
                        row += 1
                        if row >= height - 8:
                            break

                safe(screen, row, 2, "QUEUED NOTIFICATIONS", curses.A_BOLD)
                row += 1
                rows = state.pending_notifications(limit=12)
                if not rows:
                    safe(screen, row, 4, "None")
                for item in rows:
                    detail = (
                        "n"
                        + str(item["id"])
                        + "  P"
                        + str(item["priority"])
                        + "  "
                        + str(item["key"])
                        + "  "
                        + str(item["text"])
                    )
                    if item["reason"]:
                        detail += "  why=" + str(item["reason"])
                    safe(screen, row, 4, detail)
                    row += 1
                    if row >= height - 2:
                        break
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
            if key in (curses.KEY_RIGHT, curses.KEY_DOWN):
                tab = (tab + 1) % len(TABS)
                notice = ""
            elif key in (curses.KEY_LEFT, curses.KEY_UP):
                tab = (tab - 1) % len(TABS)
                notice = ""
            elif name == "MEMORY" and key in (ord("e"), ord("E")):
                notice = memory_edit_action(screen, state)
            elif name == "MEMORY" and key in (ord("d"), ord("D")):
                notice = memory_delete_action(screen, state)
            elif name == "PROACTIVE" and key in (ord("x"), ord("X")):
                selected = prompt(
                    screen,
                    "Cancel item (n<ID> notification, w<ID> watch): ",
                ).strip().lower()
                if selected.startswith("n") and selected[1:].isdigit():
                    notice = (
                        "Queued notification cancelled."
                        if state.cancel_notification(int(selected[1:]))
                        else "No pending notification with that id."
                    )
                elif selected.startswith("w") and selected[1:].isdigit():
                    notice = (
                        "Condition watch cancelled."
                        if state.cancel_condition_watch(int(selected[1:]))
                        else "No active condition watch with that id."
                    )
                else:
                    notice = "Use n<ID> or w<ID>."
            elif name == "AGENTS" and key in (ord("c"), ord("C")):
                running = next(
                    (
                        item
                        for item in state.recent_agent_runs(limit=20)
                        if str(item["status"]) == "running"
                    ),
                    None,
                )
                if running is None:
                    notice = "No running agent task."
                elif state.request_agent_cancel(int(running["id"])):
                    notice = "Cancellation requested for run #" + str(running["id"])
                else:
                    notice = "That agent run is no longer active."
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
