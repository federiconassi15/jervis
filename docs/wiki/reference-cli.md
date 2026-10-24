# Reference: CLI

## Core commands

    jervis
    jervis home
    jervis run
    jervis tui
    jervis legacy-tui
    jervis status
    jervis snapshot list
    jervis doctor
    jervis install
    jervis update-check
    jervis runtime-info
    jervis benchmark
    jervis repair audio
    jervis repair openclaw

## Jervis 8 terminal behavior

`jervis` and `jervis home` open the plain terminal menu. `jervis tui` remains a compatibility alias for that menu, while `jervis legacy-tui` explicitly opens the old fullscreen Control Deck on a capable terminal. Without an interactive terminal, the main entry point displays command hints rather than launching a TUI.

## 8.1 draft commands (not in the 8.0.1 stable download)

```text
jervis offline --style playful hello
jervis offline --no-memory "what time is it?"
jervis control-center [--port PORT]
jervis self-heal [plan] [--json]
jervis self-heal apply permissions [--yes]
jervis hypercore --iterations 250 [--json]
jervis plugins [--json]
jervis plugins run PLUGIN_ID COMMAND
jervis companion serve [--lan] [--port PORT]
jervis backup encrypt FILE.jenc
jervis backup restore-encrypted FILE.jenc
```

Read the [Evolve CLI guide](evolve-better-cli.md) before using experimental commands. The companion service is read-only and remote LAN exposure is opt-in. The dashboard is localhost-only.

## Runtime information

`jervis runtime-info` reports the active Jervis version, audio-processing backend, and whether native acceleration is active.

## Benchmark

    jervis benchmark

Measures local audio analysis, SQLite state work, and context snapshots. It also summarizes recent real runtime timing samples when they exist.

Machine-readable output:

    jervis benchmark --json

Custom sample counts:

    jervis benchmark --iterations 250 --history 200

Recent live metrics include `inference_ms`, `brain_ms`, and `command_to_reply_ms`.

The benchmark uses isolated temporary state for synthetic tests and does not write benchmark fixtures into the user's normal database.

## Related pages

- [Reference index](reference-index.md)
- [Operations](operations-index.md)
- [Troubleshooting](troubleshooting-index.md)
