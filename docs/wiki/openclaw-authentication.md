# OpenClaw: Authentication

## Jervis-owned presentation

Jervis 7.3.1 renders OpenClaw's own onboarding wizard over Gateway RPC instead of handing the terminal to OpenClaw.

The upstream wizard remains authoritative for which authentication methods are available.

## What this covers

Depending on the installed OpenClaw version and provider plugins, the wizard may offer:

- API keys
- bearer or provider tokens
- OAuth
- device-code login
- CLI credential reuse
- SecretRef-backed credentials
- custom OpenAI-compatible endpoints
- OpenAI Responses-compatible endpoints
- Anthropic-compatible endpoints
- local model servers
- plugin-provided provider authentication

Jervis does not hard-code that list. It renders what OpenClaw returns.

## Secret handling

When OpenClaw marks a text step as sensitive, Jervis renders a password-style input.

Jervis does not:

- place the secret in the review page,
- echo it in installer status text,
- write it to Jervis configuration,
- persist it in Jervis state.

The credential is submitted to the local OpenClaw wizard session and OpenClaw applies its own credential-storage policy.

## Headless authorization

Server installs use the same in-Jervis wizard. Authorization URLs, codes, and instructions supplied by OpenClaw are displayed inside the Jervis control deck, so a user can approve access from another browser/device when required.

## Future providers

A newly added OpenClaw provider does not require a Jervis release merely to appear in setup. If the installed OpenClaw version exposes it through the wizard protocol, Jervis renders it automatically.

## Related pages

- [OpenClaw index](openclaw-index.md)
- [Installer: OpenClaw Setup](installer-openclaw-install.md)
- [Getting Started: OpenClaw Setup](getting-started-openclaw-setup.md)
