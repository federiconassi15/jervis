# Installer: OpenClaw Setup

Jervis 7.3.1 owns the visible OpenClaw onboarding experience.

## Design

The installer does **not** maintain its own provider/API list.

After the Jervis core install is verified, Jervis:

1. quietly installs OpenClaw if it is missing,
2. starts an isolated loopback-only temporary OpenClaw Gateway,
3. starts OpenClaw's own `wizard.start` onboarding session,
4. renders each upstream wizard step inside the Jervis Installation Control Deck,
5. submits answers with `wizard.next`,
6. closes the temporary Gateway when onboarding completes.

Because OpenClaw supplies the wizard steps at runtime, Jervis automatically inherits current and future built-in providers, plugin-provided providers, API-key/token flows, OAuth/device-code flows, custom endpoints, channels, search providers, skills, Gateway configuration, daemon choices, and other onboarding additions supported by that OpenClaw release.

## Supported wizard controls

Jervis currently renders every OpenClaw wizard step family:

- note
- text
- sensitive text / API-key input
- select
- confirm
- multiselect
- progress
- action

Sensitive text fields are masked. Their values are never shown in the Jervis review screen or normal installer logs.

## Headless behavior

The same renderer is used in Desktop and Server mode.

If an upstream provider offers a device-code or browser authorization flow, OpenClaw sends the authorization URL/code through the wizard session and Jervis displays it inside the control deck. A headless user can complete the authorization from another device without leaving the Jervis setup flow.

## Provider coverage

Provider coverage is intentionally **OpenClaw-defined**, not Jervis-defined.

That means there is no static "supported APIs" list in Jervis to become stale. Providers added by a newer OpenClaw release or an installed provider plugin appear when OpenClaw includes them in its wizard.

## Failure behavior

The Jervis core remains installed if OpenClaw onboarding fails. The installer shows a retry action and explains that upstream OpenClaw may already have saved earlier wizard answers; Jervis does not claim those writes were rolled back.

## Related pages

- [OpenClaw Authentication](openclaw-authentication.md)
- [Getting Started: OpenClaw Setup](getting-started-openclaw-setup.md)
- [Installer index](installer-index.md)
- [Wiki Home](Home.md)
