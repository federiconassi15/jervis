# Jervis Vision 8.2 — opt-in image intake foundation

**Not a live screenshot, OCR or vision model integration.** Only user-selected,
locally accessible PNG/JPEG files with explicit consent and an authenticated
\`filesystem.read\` capability grant may enter memory for downstream use.
Size, dimensions, pixel count, regular-file and symlink checks are enforced.

The current header checks only determine reported format and dimensions;
they do **not** fully decode, authenticate or sanitize image structure.
Actual decoders and any cloud provider adapters must validate independently
in a separately permissioned, resource-limited process. No content is written
or uploaded by this module, and no image bytes are put into logs.

A future screenshot adapter must request real OS capture permissions and a
fresh \`screen.capture\` grant for each authorized capture session. On Wayland
this should use the desktop portal. Windows and macOS require the respective
native screen permission and window isolation policies. Never implement
stealth/background capture, and never assume a paired phone may view the
host screen without additional explicit consent.
