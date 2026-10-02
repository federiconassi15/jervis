import asyncio

import jervis.installer as installer_module
from jervis.install_plan import InstallPlan
from jervis.installer import JervisInstaller, _terminal_cue, install


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
            assert app.query_one("#brain-wizard") is not None

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


def test_installer_arrow_navigation():
    async def scenario():
        app = JervisInstaller()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            assert app.step == 0
            assert app.mode_choice == "desktop"
            assert app.query_one("#mode-server").display is True
            await pilot.click("#mode-server")
            await pilot.pause()
            assert app.mode_choice == "server"

            app.query_one("#next").focus()
            await pilot.press("right")
            await pilot.pause()
            assert app.step == 1

            app.query_one("#back").focus()
            await pilot.press("left")
            await pilot.pause()
            assert app.step == 0

    asyncio.run(scenario())


def test_terminal_cues_can_be_disabled(monkeypatch):
    monkeypatch.setenv("JERVIS_TERMINAL_CUES", "0")
    _terminal_cue("attention")


def test_openclaw_sensitive_text_step_is_masked():
    async def scenario():
        app = JervisInstaller()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            app._switch(5)
            app._render_openclaw_wizard_step(
                {
                    "id": "future-api-key",
                    "type": "text",
                    "title": "Future Provider",
                    "message": "Enter API key",
                    "sensitive": True,
                }
            )
            field = app.query_one("#openclaw-wizard-input")
            assert field.password is True
            assert field.display is True

    asyncio.run(scenario())


def test_openclaw_future_provider_select_is_data_driven():
    async def scenario():
        app = JervisInstaller()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            app._switch(5)
            value = {"provider": "future-provider", "method": "magic"}
            app._render_openclaw_wizard_step(
                {
                    "id": "provider",
                    "type": "select",
                    "message": "Choose provider",
                    "options": [
                        {
                            "label": "Future Provider",
                            "hint": "Added by a future OpenClaw/plugin release",
                            "value": value,
                        }
                    ],
                }
            )
            assert app.openclaw_wizard_option_values == [value]
            assert app.query_one("#openclaw-wizard-select").display is True

    asyncio.run(scenario())


def test_openclaw_multiselect_renders_arbitrary_options():
    async def scenario():
        app = JervisInstaller()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            app._switch(5)
            app._render_openclaw_wizard_step(
                {
                    "id": "channels",
                    "type": "multiselect",
                    "message": "Choose channels",
                    "options": [
                        {"label": "Alpha", "value": "alpha"},
                        {"label": "Beta", "value": "beta"},
                    ],
                    "initialValue": ["beta"],
                }
            )
            assert app.openclaw_wizard_option_values == ["alpha", "beta"]
            assert app.query_one("#openclaw-wizard-input").value == "2"

    asyncio.run(scenario())


def test_installer_layout_survives_live_terminal_resize():
    async def scenario():
        app = JervisInstaller()
        async with app.run_test(size=(110, 34)) as pilot:
            await pilot.pause()
            assert app.query_one("#sidebar").display is True
            assert app.query_one("#mode-server").display is True
            assert "Deployment" in str(app.query_one("#stepbar").render())

            await pilot.resize_terminal(72, 20)
            await pilot.pause()
            assert app.query_one("#sidebar").display is True
            assert app.query_one("#next").region.bottom <= app.screen.size.height

            await pilot.resize_terminal(50, 16)
            await pilot.pause()
            assert app.query_one("#compact-stage").display is True
            assert "DEPLOYMENT" in str(app.query_one("#compact-stage").render())
            assert app.query_one("#next").region.bottom <= app.screen.size.height

            await pilot.resize_terminal(100, 30)
            await pilot.pause()
            assert app.query_one("#sidebar").display is True
            assert app.query_one("#next").region.bottom <= app.screen.size.height

    asyncio.run(scenario())


def test_installer_server_mode_is_first_class_visible_choice():
    async def scenario():
        app = JervisInstaller()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            server = app.query_one("#mode-server")
            assert server.display is True
            assert server.region.height > 1
            await pilot.click("#mode-server")
            await pilot.pause()
            assert app.mode_choice == "server"
            assert server.has_class("selected")

    asyncio.run(scenario())
