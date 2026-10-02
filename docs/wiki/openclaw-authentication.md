# OpenClaw: Authentication

Jervis 7.3.1 can configure OpenClaw authentication from inside the Jervis installer.

## Headless ChatGPT / Codex

Desktop mode uses browser OAuth.

Server mode uses OpenClaw's device-code login so a headless host can display the authorization code while approval happens on another device.

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
