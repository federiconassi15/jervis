# Jervis

> A lightweight, always-on voice assistant for local hardware, OpenClaw, and agentic workflows.

Jervis is an open-source voice assistant designed to feel fast, conversational, and useful on modest hardware. It combines local wake-word detection and speech processing with an external agentic brain, a terminal control deck, multi-user identity, permissions, skills, proactive events, and repair tooling.

> [!IMPORTANT]
> Jervis is under active development. The repository is being prepared for its first public release; the production runtime and generic installer will be published separately.

## Why Jervis?

Most voice assistants either depend heavily on the cloud or assume powerful hardware. Jervis is built around a different idea:

- **Fast by default** — wake words, simple commands, cues, and routing stay local.
- **Low-resource** — designed to run on modest Linux hardware.
- **Conversational** — follow-ups, interruption, speaker sessions, and natural dialogue.
- **Private where possible** — identity and local state remain local when practical.
- **Hackable** — skills, agents, MCP integrations, and configuration are first-class.
- **Recoverable** — component-level diagnostics and repair instead of rebooting everything.

## Planned architecture

```text
Microphone
   │
   ▼
Wake / AEC / VAD
   │
   ▼
Speaker + Session Manager
   │
   ▼
Intent Router
   ├── Local command
   ├── Prerecorded response
   ├── Skill
   ├── MCP / agent
   └── OpenClaw brain
           │
           ▼
   Response Manager
           │
           ▼
 Interruptible TTS
```

Supporting services include identity, permissions, per-user memory, event history, health monitoring, proactive alerts, and the Jervis Control Deck.

## Current direction

The next public milestone is **Jervis 7.1**, focused on making conversation and speaker recognition substantially more reliable:

- trusted conversation sessions
- stronger speaker recognition from longer utterances
- retry-before-password authentication
- continuous high-confidence voice learning
- conversation lock-on between follow-ups
- a short **"Boss?"** wake acknowledgement

See [docs/ROADMAP.md](docs/ROADMAP.md) for the broader plan.

## Installation

The public installer is **not available yet**.

Please do not copy private or machine-specific development installers into a new system. A clean, generic installer will be published here once the project structure and migration path are ready.

## Configuration

A safe starter configuration is available in [config.example.json](config.example.json).

Never commit:

- API keys or tokens
- authentication passphrases or hashes
- speaker voiceprints
- private conversation history
- device serial numbers
- personal filesystem paths
- machine-specific credentials

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

For security issues, see [SECURITY.md](SECURITY.md).

## License

Jervis is licensed under the **GNU General Public License v3.0**. See [LICENSE](LICENSE).

## Credits

Created by **Federico Nassi**.

Development has included AI-assisted coding, debugging, architecture work, and documentation. AI assistance does not replace human authorship, review, or responsibility for the project.

---

**Jervis is not affiliated with Marvel, Iron Man, or any related trademark holder.**
