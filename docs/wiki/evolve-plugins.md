# Plugin System — data-only first

**State:** 8.1 draft supports validated manifest discovery and a restricted declarative response action. No third-party Python, shell script or dynamic code is executed.

Plugin packages go under the local Jervis data directory's `plugins/<name>/plugin.json`. Example:

```json
{
  "id": "demo.greeter",
  "version": "1.0.0",
  "description": "Local greeting",
  "permissions": [],
  "commands": [
    {"name": "greet", "type": "response", "text": "Hello from the demo plugin."}
  ]
}
```

Use `jervis plugins` to list validated manifests, `jervis plugins --json` for machine-readable output, or `jervis plugins run demo.greeter greet` to render a **static** response. Manifest size, permission IDs, action count, names, and symlinks are bounded and checked. Only known actions are supported.

## Important limitation

This is a secure foundation for the plugin system, **not** arbitrary-code plugin execution. A future executable plugin runtime needs explicit capabilities, sandboxing, user permission prompts, quotas and cross-platform security tests. It is not safe to treat manifest acceptance as code-execution permission.
