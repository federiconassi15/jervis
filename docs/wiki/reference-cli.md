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
