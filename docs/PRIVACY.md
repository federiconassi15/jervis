# Privacy

Jervis is intended to keep as much assistant state local as practical.

## Data categories

Depending on configuration, Jervis may process:

- live microphone audio
- speech transcripts
- speaker embeddings or voiceprints
- local conversation history
- user preferences and permissions
- external AI requests and responses

## Recommended defaults

- Do not persist raw microphone audio.
- Store authentication secrets only as appropriate cryptographic verifiers, never plaintext.
- Keep biometric/speaker data local.
- Redact authentication content from dialogue logs.
- Keep histories bounded and provide clear deletion controls.
- Send only the context required for a remote AI request.

## External providers

When Jervis routes a request to OpenClaw, an MCP server, or another external provider, that provider may receive the text or data required to complete the request. Users should review the privacy policy and configuration of every provider they connect.

## Repository hygiene

Never commit real credentials, speaker data, personal conversation logs, or recordings to this repository.
