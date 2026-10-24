# Better CLI — Jervis 8.1 commands

**State:** new explicit subcommands implemented in the draft. The normal `jervis` home menu stays plain and keyboard accessible; no fullscreen TUI requirement.

```sh
jervis --help
jervis offline --style balanced hello
jervis health
jervis control-center
jervis self-heal plan
jervis self-heal apply permissions
jervis hypercore --iterations 250
jervis plugins --json
jervis plugins run example.plugin greet
jervis companion serve --port 8766
jervis backup encrypt my-backup.jenc
jervis backup restore-encrypted my-backup.jenc
```

Use `jervis legacy-tui` only when the old Control Deck is needed. Encrypted backup commands prompt for the passphrase on a local terminal and do not accept a passphrase as a command-line argument.

The existing `jervis doctor`, `jervis repair-center`, `jervis status`, and snapshot/rollback commands remain available.

[CLI reference](reference-cli.md)
