# Jervis 8.2 — outbound-only relay (experimental)

**Do not deploy as a public production service.** The Worker/Durable Object
provides a bounded authenticated *transport* for Jervis instances and Android
devices. It does not implement device consent, end-to-end encryption, host
command authorization, Android clients, or secure key storage. Those are
blocking requirements before remote chat or control may be enabled.

## No port forwarding

The host and Android client both open **outbound TLS WebSocket connections**
to a Cloudflare Worker endpoint. The Durable Object routes ephemeral opaque
frames. No inbound port, public IP address, or router configuration is needed.
Messages are not queued when either participant is offline.

## Configuration and API (private experimental testing only)

Deploy under an account-owned Cloudflare Worker, and configure
\`RELAY_ADMIN_SECRET\` using the Cloudflare secrets workflow, not a committed
file. Use a separate 256-bit random lowercase hex token per host and Android
device. Do not pass tokens in query strings, QR screenshots or logs.

1. \`POST /v1/<32hex-instance-id>/init\` with header
   \`X-Relay-Admin: <secret>\` and JSON \`{"host_token":"<64hex>"}\`.
   This works only once per instance.
2. \`POST /v1/<id>/grant\` with host bearer and JSON
   \`{"device_id":"<32hex>","token":"<64hex>"}\`.
   **Grant only after local owner-confirmed pairing.**
3. \`POST /v1/<id>/revoke\` with host bearer and device identifier.
4. \`GET /v1/<id>/connect\` via TLS WebSocket with an Authorization Bearer
   header. One host and at most eight devices per instance.

Messages have exactly \`{v:1,kind:"handshake"|"ciphertext",
id:"<32hex>",seq:<nonnegative-int>,body:"<base64url>"}\`.
The relay does not parse the encrypted body or execute anything. Clients
must validate identity-bound E2E key negotiation, authenticated encryption,
session replay and monotonic sequence numbers. The host must reauthorize
each actual action. The Worker admin secret is a *deployment secret*, not
a host/device authentication replacement.

Deploying requires a Cloudflare account, owned Worker namespace and secret
provisioning. The repo intentionally contains no live credentials. The
host relay client and Android secure pairing UI do not exist yet.

## Validation

Run \`npm test\` inside \`relay/\` using Node 22+. Additional mandatory gates:
Cloudflare Wrangler local Durable Object integration, replay/fuzz/rate tests,
device revocation and reconnect, network transitions, cryptographic protocol
audit, real Android + host testing, privacy and cost review.
