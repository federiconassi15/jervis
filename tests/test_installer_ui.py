import asyncio

import jervis.installer as installer_module
from jervis.install_plan import InstallPlan
from jervis.installer import JervisInstaller, install


def test_install_plan_validation():
    plan = InstallPlan(
        mode="desktop",
        source_kind="desktop",
        input_device=0,
        output_device=1,
        owner_name="Example",
        honorific="sir",
        passphrase="correct horse battery staple",
    )
    plan.validate()


def test_installer_entrypoint_exists():
    assert callable(install)


def test_installer_tui_mounts_and_mouse_navigates():
    async def scenario():
        app = JervisInstaller()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            assert app.step == 0
            next_button = app.query_one("#next")
            assert next_button.region.bottom <= app.screen.size.height
            clicked = await pilot.click("#next")
            assert clicked
            await pilot.pause()
            assert app.step == 1
            assert app.query_one("#openclaw-auth") is not None

    asyncio.run(scenario())


def test_installer_exit_code_propagates(monkeypatch):
    monkeypatch.setattr(installer_module, "ensure_linux_audio", lambda prompt: None)
    monkeypatch.setattr(JervisInstaller, "run", lambda self, mouse=True: 0)
    assert install() == 0

    monkeypatch.setattr(JervisInstaller, "run", lambda self, mouse=True: 130)
    assert install() == 130

    monkeypatch.setattr(JervisInstaller, "run", lambda self, mouse=True: None)
    assert install() == 130


def test_quit_is_success_after_core_install(monkeypatch):
    app = JervisInstaller()
    results = []
    monkeypatch.setattr(app, "exit", lambda result=None: results.append(result))

    app.core_installed = False
    app.action_quit()
    assert results[-1] == 130

    app.core_installed = True
    app.action_quit()
    assert results[-1] == 0


def test_linux_prerequisites_run_before_tui(monkeypatch):
    order = []

    monkeypatch.setattr(
        installer_module,
        "ensure_linux_audio",
        lambda prompt: order.append("prerequisites"),
    )
    monkeypatch.setattr(
        JervisInstaller,
        "run",
        lambda self, mouse=True: order.append("tui") or 0,
    )

    assert install() == 0
    assert order == ["prerequisites", "tui"]
