# Jervis 8.2 signed Skill Marketplace (experimental)

This is a **local installation primitive**, not a public marketplace or
an executable plugin sandbox. It accepts a bounded manifest, detached
Ed25519 signature, and a trusted publisher public key obtained independently.
The owner must explicitly approve each installation. Valid signatures prove
package origin, not that the content deserves any permissions.

Only declarative \`response\` commands with \`permissions: []\` can be installed.
Executable Python/WASM, shell scripts, network access, dependencies, dynamic
plugin loading, remote downloads and silent auto-updates are deliberately not
supported. Installed plugins stay compatible with the 8.1 static plugin
discovery engine. Plugin IDs and version fields are strictly validated, and
an already installed plugin can never be silently overwritten.

Future work: permission-scoped sandbox evaluation, reviewable publisher
registry and revocation, cross-platform atomic uninstall and updates, audit
logging, dependency policy, curated catalog, offline cache, UI and full
malicious-input testing. Legacy trusted Python skills are not migrated or
made sandboxed by this feature.
