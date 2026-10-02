# Operations: Doctor & Diagnostics

Start with:

    jervis doctor

Create a sanitized support bundle at the same time:

    jervis doctor --bundle

Or choose an output path:

    jervis diagnostics ./jervis-support.zip

## Bundle contents

The 7.3.5 diagnostics bundle contains structured status, doctor results, permission/capability information and a redacted configuration view.

Raw logs are **not** included by default because they may contain transcripts, device identifiers, provider information or private paths.

Sensitive keys/tokens/passwords/passphrases/credentials and device serial fields are redacted. Home-directory paths are normalized to `~` and common private IPv4 ranges are masked.

## Related checks

    jervis status
    jervis permissions
    jervis acceptance-test
    jervis openclaw-compat

[Back to Operations](operations-index.md)
