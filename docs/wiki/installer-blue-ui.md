# Installer: Installation Control Deck

## Purpose

Jervis 7.3.1 upgrades the installer presentation into a terminal-oriented **Installation Control Deck** while preserving the same cross-platform transactional install engine.

The design deliberately uses Unicode lines, rails, boxes, status glyphs, and compact animation rather than a graphical desktop installer. It should feel native to a terminal without becoming difficult to read.

## Header

    ┌─ SYSTEM BOOTSTRAP // JERVIS 7.3.1 ─┐

    ◐   ╭──────────── J  E  R  V  I  S ────────────╮
        │        INSTALLATION CONTROL DECK         │
        ╰──────────────────────────────────────────╯

## Stage rail

Completed stages use ✓, the active stage uses boxed markers, and future stages use a dot.

    ✓01 MODE ── ╢02 BRAIN╟ ── ·03 AUDIO ── ·04 IDENTITY

The compact-terminal test remains part of CI so framing cannot silently overflow the supported 100×30 test surface.

## Major states

Important transitions use explicit framed status for systems ready, subsystem switches, installation, attention/rollback, OpenClaw sign-in, and completion.

## Security

The visual layer must never expose passphrases, provider secrets, voiceprints, private transcripts, or machine-specific personal data.

## Related pages

- [Installer index](installer-index.md)
- [Banter & terminal cues](installer-banter.md)
- [Transaction model](installer-transaction-model.md)
- [Rollback](installer-rollback.md)
