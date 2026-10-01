from __future__ import annotations

from pathlib import Path

import pytest

from jervis.install_engine import _reconcile_startup
from jervis.install_tx import InstallTransaction
from jervis.models import Health


class FakePlatform:
    def __init__(self, installed: bool):
        self.installed = installed
        self.mode = "desktop" if installed else None
        self.events = []

    def service_installed(self):
        return self.installed

    def service_health(self):
        return Health(self.installed, "service", "test")

    def install_service(self, executable, env, mode="desktop"):
        self.events.append(("install", mode, str(executable), dict(env)))
        self.installed = True
        self.mode = mode

    def remove_service(self):
        self.events.append(("remove", self.mode))
        self.installed = False
        self.mode = None


def test_autostart_can_be_disabled_transactionally():
    platform = FakePlatform(installed=True)
    with InstallTransaction(platform) as transaction:
        _reconcile_startup(
            platform,
            transaction,
            Path("/jervis"),
            {"JERVIS_HOME": "/home"},
            "desktop",
            False,
            "desktop",
        )
        transaction.commit()

    assert not platform.installed
    assert platform.events == [("remove", "desktop")]


def test_mode_change_replaces_startup_definition():
    platform = FakePlatform(installed=True)
    with InstallTransaction(platform) as transaction:
        _reconcile_startup(
            platform,
            transaction,
            Path("/jervis"),
            {"JERVIS_HOME": "/home"},
            "server",
            True,
            "desktop",
        )
        transaction.commit()

    assert platform.installed
    assert platform.mode == "server"
    assert platform.events[0] == ("remove", "desktop")
    assert platform.events[1][0:2] == ("install", "server")


def test_failed_mode_change_restores_previous_startup():
    platform = FakePlatform(installed=True)

    with pytest.raises(RuntimeError):
        with InstallTransaction(platform) as transaction:
            _reconcile_startup(
                platform,
                transaction,
                Path("/jervis"),
                {"JERVIS_HOME": "/home"},
                "server",
                True,
                "desktop",
            )
            raise RuntimeError("later install step failed")

    assert platform.installed
    assert platform.mode == "desktop"
    assert platform.events[-1][0:2] == ("install", "desktop")
