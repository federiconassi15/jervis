import importlib

import pytest


MODULES = [
    "jervis.agents",
    "jervis.audio.android",
    "jervis.audio.desktop",
    "jervis.audio.devices",
    "jervis.brain.openclaw",
    "jervis.benchmark",
    "jervis.cli",
    "jervis.config",
    "jervis.doctor",
    "jervis.identity",
    "jervis.fast",
    "jervis.install_tx",
    "jervis.installer",
    "jervis.models",
    "jervis.openclaw_setup",
    "jervis.openclaw_wizard",
    "jervis.paths",
    "jervis.permissions",
    "jervis.router",
    "jervis.repair",
    "jervis.presence",
    "jervis.platforms.factory",
    "jervis.platforms.linux",
    "jervis.platforms.macos",
    "jervis.platforms.windows",
    "jervis.prereqs",
    "jervis.proactive",
    "jervis.resilience",
    "jervis.runtime",
    "jervis.security",
    "jervis.sessions",
    "jervis.skills",
    "jervis.speaker",
    "jervis.speaker_model",
    "jervis.speech.stt",
    "jervis.speech.tts",
    "jervis.speech.vad",
    "jervis.speech.wake",
    "jervis.state",
    "jervis.tui",
    "jervis.updater",
]


@pytest.mark.parametrize("module", MODULES)
def test_module_imports(module):
    importlib.import_module(module)
