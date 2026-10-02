# Installer: OpenClaw Setup

Jervis 7.3.1 owns the OpenClaw first-run experience. The user answers OpenClaw setup questions inside the Jervis Installation Control Deck rather than being dropped into the raw OpenClaw wizard.

## What Jervis collects

The Brain step can collect and apply:

- model provider / authentication route
- provider API key or token where required
- OpenClaw agent name
- custom-provider base URL, model ID, provider ID, compatibility mode, and image-input capability
- Gateway bind mode
- Gateway authentication mode and credential
- Gateway daemon install choice
- daemon runtime (Node or Bun)
- Node package manager for skills
- optional skills, hooks, channels, and web-search setup choices
- explicit acknowledgement of OpenClaw's agent/system-access risk

Provider and Gateway secrets are masked in the installer and are never shown on the final review screen.

## Supported model/auth routes

Jervis currently exposes:

- ChatGPT / Codex subscription
- OpenAI API key
- Anthropic API key
- Google Gemini API key
- OpenRouter API key
- Mistral API key
- Z.AI API key
- xAI / Grok OAuth
- GitHub Copilot token
- custom OpenAI-compatible, OpenAI Responses-compatible, or Anthropic-compatible providers
- Ollama
- LM Studio
- configure later

API-key, token, custom, and local-provider paths are driven through OpenClaw's supported non-interactive onboarding interface.

## External authorization

Browser/device authorization cannot be replaced by a local installer form. ChatGPT/Codex and xAI OAuth therefore finish with an explicit Jervis authorization step after the core install.

Server-mode ChatGPT/Codex authorization uses device code so the Gateway host can remain headless.

## No raw OpenClaw wizard

For automated provider paths Jervis invokes OpenClaw with non-interactive onboarding and suppresses the OpenClaw UI. If OpenClaw cannot complete a selected path without an external authorization or capability review, Jervis reports that state instead of silently opening another wizard.

## Safety

Jervis does not auto-accept OpenClaw's agent/system-access warning. The user must explicitly acknowledge it in the Jervis installer.

## Related pages

- [Installer index](installer-index.md)
- [OpenClaw Authentication](openclaw-authentication.md)
- [Getting Started: OpenClaw Setup](getting-started-openclaw-setup.md)
