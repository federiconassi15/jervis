# Getting Started: OpenClaw Setup

OpenClaw setup is integrated into the Jervis installer.

## Brain step

Choose your provider, enter any required credential, configure the Gateway, and choose daemon/runtime options without leaving the Jervis Installation Control Deck.

For API-key, token, custom-provider, Ollama, and LM Studio routes, Jervis runs OpenClaw onboarding non-interactively behind the scenes.

For ChatGPT/Codex or xAI OAuth, Jervis completes every local configuration choice first and then asks for the unavoidable external account authorization.

## Headless servers

For a Server install using ChatGPT/Codex, Jervis selects device-code authentication. You can approve the code in a browser on another computer or phone while the server remains headless.

## Any OpenClaw provider

The provider picker contains a large built-in catalog. If the provider you need is newer than the installed Jervis catalog, choose **Any OpenClaw provider · advanced pass-through**.

Enter the auth-choice id documented by OpenClaw and, if needed, the provider's credential environment-variable name and official plugin package. Jervis keeps the flow non-interactive and behind the Installation Control Deck.

## Provider secrets

Secrets are masked while typing and are not shown on the review screen.

## Risk acknowledgement

OpenClaw agents can use tools and system access. Jervis requires the user to explicitly acknowledge that warning before setup can continue.

## Troubleshooting

If hidden onboarding fails, Jervis reports the OpenClaw error while preserving the Jervis installation boundary. Run `openclaw doctor` for provider/Gateway diagnostics after installation.

[Back to Getting Started](getting-started-index.md)
