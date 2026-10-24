# Control Center — private web dashboard

**State:** an authenticated, read-only loopback web dashboard is implemented in the 8.1 draft.

```sh
jervis control-center
jervis control-center --port 8765
```

The CLI prints a private one-process URL. Open it in a browser **on the same machine**. Jervis binds only to `127.0.0.1`, not to a LAN address. The session uses an HttpOnly SameSite cookie, origin/host restrictions, cache-control headers and a private unlock token. No third-party scripts or external assets are loaded.

The dashboard displays the Jervis version, configuration/database presence, validated snapshot counts, plugin manifest counts and recent recorded latency. It does **not** reveal private transcripts, credentials, device IDs, file paths, identity details, or configuration values.

The dashboard does not yet provide account management, config editing, interactive repair or updates. Use the CLI for those and treat requests for write access as a separate security review.

[Companion status](evolve-companion.md) is served by a different, opt-in TLS server; this local dashboard is never exposed remotely.
