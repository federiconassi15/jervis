# OpenClaw: Authentication

Jervis 7.3.1 can configure OpenClaw authentication from inside the Jervis installer.

## Headless ChatGPT / Codex

Desktop mode uses browser OAuth.

Server mode uses OpenClaw's device-code login so a headless host can display the authorization code while approval happens on another device.

## Provider catalog and future APIs

Jervis ships a current OpenClaw provider catalog for common API-key, hosted-gateway, custom, and local-model routes.

The catalog is not a hard compatibility boundary. The installer also exposes a universal OpenClaw provider mode that accepts a future OpenClaw auth-choice id, credential environment-variable name, and optional official plugin package. This lets a newly released OpenClaw API/provider work before Jervis has a dedicated label for it.

Official external provider plugins are installed non-interactively only after the user explicitly approves their capability consent in the Jervis installer.

Provider credentials are passed through process environment where supported instead of embedding secrets in OpenClaw command-line arguments.

## API-key providers

The installer has first-class routes for OpenAI, Anthropic, Gemini, OpenRouter, Mistral, Z.AI, and GitHub Copilot token authentication.

Secrets are entered through masked Jervis fields and are omitted from Jervis review output and dataclass representations.

## Custom and local providers

Custom providers can specify:

- base URL
- model ID
- optional provider ID
- OpenAI chat/completions, OpenAI Responses, or Anthropic compatibility
- text-only or image-capable input

Ollama and LM Studio can also be configured from the same Brain step.

## Gateway authentication

Jervis can ask OpenClaw to:

- generate a Gateway token
- use a supplied Gateway token
- use a supplied Gateway password

Gateway bind choices include loopback, auto, LAN, and Tailnet.

## External authorization boundary

OAuth/device-code approval remains an external account-provider action. Jervis keeps the setup state and returns to the Installation Control Deck after authorization.

## Security

Never paste provider secrets into issue reports, logs, screenshots, or committed configuration examples.

[Back to OpenClaw index](openclaw-index.md)
