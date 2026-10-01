import asyncio

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
