# Offline Commands

**State:** approved phrase recognition and local responses are implemented in the 8.1 draft.

Try `jervis offline hello`, `jervis offline help`, `jervis offline "what time is it?"`, `jervis offline status`, or `jervis offline diagnostics`. The time answer comes from the machine's actual clock.

Unknown or destructive phrases are rejected instead of being guessed. Offline commands are a small, enumerated set; normal Jervis skills, reminders and voice tasks continue through their established permission and authentication layers.

For an expressive but auditable response, select `--style balanced`, `playful`, or `focused`. You can turn response history off with `--no-memory`.

[Adaptive dialogue](evolve-local-dialogue.md)
