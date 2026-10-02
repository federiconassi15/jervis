# Getting Started: OpenClaw Setup

During Jervis installation, choose:

- **Full OpenClaw guided setup** — recommended
- **Configure OpenClaw later**

## Full guided setup

You stay inside the Jervis Installation Control Deck.

After the Jervis core is installed, Jervis loads OpenClaw's live onboarding wizard and displays its questions directly. This includes provider/API selection, authentication, model selection, custom endpoints, Gateway setup, channels, search, skills, daemon/service setup, and any provider-plugin prompts exposed by the installed OpenClaw version.

You should not see the raw OpenClaw terminal wizard.

## API/provider support

Jervis does not ship a frozen provider list.

The installed OpenClaw version decides what providers and API/auth methods exist. As OpenClaw or its provider plugins add new options, they appear in the Jervis installer automatically through the wizard protocol.

## Headless servers

Browser and device-code authorization instructions are shown in Jervis. Complete the requested authorization from another device and continue the Jervis setup.

## If setup fails

Jervis remains installed. Choose **Retry OpenClaw setup** to start the upstream wizard again, or finish and configure OpenClaw later.

Earlier OpenClaw wizard answers may already have been saved before a failure.

## Related pages

- [Getting Started index](getting-started-index.md)
- [OpenClaw Authentication](openclaw-authentication.md)
- [Installer: OpenClaw Setup](installer-openclaw-install.md)
