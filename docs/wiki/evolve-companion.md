# Companion Mode — TLS read-only pairing

**State:** a deliberately restricted remote status protocol is implemented in the 8.1 draft. It is **not** a remote-control or remote-microphone service yet.

```sh
jervis companion serve
jervis companion serve --lan --port 8766
```

Without `--lan`, the server binds only to localhost. With `--lan`, it explicitly binds to all interfaces. Use only on a trusted LAN, and restrict the port using your firewall. The server generates an ephemeral TLS certificate, displays its SHA-256 fingerprint, and issues an eight-digit, five-minute, one-use pairing code. At most five failed pairing attempts are accepted.

**Verify the exact certificate fingerprint on the client against the console** before entering the code. Do not bypass certificate checks for real use. A paired client can request a bearer token via HTTPS `POST /pair` with JSON `{"code":"12345678"}`, then request `GET /api/status` with its Bearer token. The token is scoped to read-only status, expires after eight hours, and is discarded on server restart. `GET /certificate` exposes the public certificate for fingerprint comparison.

No audio, transcript, command, repair, filesystem, or credential endpoints exist. Pairing is currently ephemeral and lacks a graphical device-onboarding app or microphone transport. Those require separate testing before a full Companion Mode release.

[Security gates](evolve-security-and-testing.md)
