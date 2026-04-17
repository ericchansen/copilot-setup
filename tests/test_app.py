"""Smoke tests for the Textual TUI app."""

from __future__ import annotations

import asyncio

import pytest

from copilotsetup.app import CopilotSetupApp


@pytest.fixture
def app():
    return CopilotSetupApp()


class TestAppCompose:
    """Test that the app composes correctly (no real data needed)."""

    def test_app_has_tabs(self):
        async def _test():
            app = CopilotSetupApp()
            async with app.run_test():
                tabs = app.query("TabPane")
                assert len(tabs) == 5
                tab_ids = {t.id for t in tabs}
                assert tab_ids == {"sources", "servers", "skills", "plugins", "lsp"}

        asyncio.run(_test())

    def test_app_has_data_tables(self):
        async def _test():
            app = CopilotSetupApp()
            async with app.run_test():
                tables = app.query("DataTable")
                assert len(tables) == 5

        asyncio.run(_test())

    def test_app_has_footer(self):
        async def _test():
            app = CopilotSetupApp()
            async with app.run_test():
                footers = app.query("Footer")
                assert len(footers) == 1

        asyncio.run(_test())

    def test_app_has_detail_panes(self):
        async def _test():
            from copilotsetup.widgets.detail_pane import DetailPane

            app = CopilotSetupApp()
            async with app.run_test():
                panes = app.query(DetailPane)
                assert len(panes) == 5
                # All visible by default (winget-tui 2-pane style)
                for pane in panes:
                    assert pane.display

        asyncio.run(_test())


class TestPluginUpgradeFlow:
    """Pilot-driven tests for the upgrade action: stub `shutil.which` and
    `subprocess.run` to avoid actually shelling out to the copilot CLI."""

    def test_upgrade_success_reloads_state(self, monkeypatch):
        async def _test():
            import shutil as _shutil
            import subprocess as _subprocess

            calls: list[list[str]] = []

            class _OK:
                returncode = 0
                stdout = "Updated msx-mcp"
                stderr = ""

            def _fake_run(cmd, **kw):
                calls.append(cmd)
                return _OK()

            monkeypatch.setattr(_shutil, "which", lambda name: "/fake/copilot")
            monkeypatch.setattr(_subprocess, "run", _fake_run)
            reloaded = []
            monkeypatch.setattr(
                CopilotSetupApp,
                "_load_state",
                lambda self: reloaded.append(True),
                raising=False,
            )

            app = CopilotSetupApp()
            async with app.run_test() as pilot:
                # Clear the on_mount call before invoking the upgrade.
                reloaded.clear()
                app._run_plugin_upgrade("msx-mcp")
                await app.workers.wait_for_complete()
                await pilot.pause()
                assert calls == [["/fake/copilot", "plugin", "update", "msx-mcp"]]
                assert reloaded == [True]

        asyncio.run(_test())

    def test_upgrade_nonzero_exit_shows_error(self, monkeypatch):
        async def _test():
            import shutil as _shutil
            import subprocess as _subprocess

            class _Bad:
                returncode = 1
                stdout = ""
                stderr = "boom: something failed\n"

            monkeypatch.setattr(_shutil, "which", lambda name: "/fake/copilot")
            monkeypatch.setattr(_subprocess, "run", lambda *a, **kw: _Bad())
            monkeypatch.setattr(CopilotSetupApp, "_load_state", lambda self: None, raising=False)

            statuses: list[tuple[str, str]] = []
            orig = CopilotSetupApp._notify_status

            def _capture(self, text, severity="information"):
                statuses.append((text, severity))
                orig(self, text, severity)

            monkeypatch.setattr(CopilotSetupApp, "_notify_status", _capture, raising=False)

            app = CopilotSetupApp()
            async with app.run_test() as pilot:
                app._run_plugin_upgrade("msx-mcp")
                await app.workers.wait_for_complete()
                await pilot.pause()
                assert any("boom: something failed" in t and sev == "error" for t, sev in statuses)

        asyncio.run(_test())

    def test_upgrade_missing_copilot_binary(self, monkeypatch):
        async def _test():
            import shutil as _shutil

            monkeypatch.setattr(_shutil, "which", lambda name: None)
            monkeypatch.setattr(CopilotSetupApp, "_load_state", lambda self: None, raising=False)

            statuses: list[tuple[str, str]] = []
            orig = CopilotSetupApp._notify_status

            def _capture(self, text, severity="information"):
                statuses.append((text, severity))
                orig(self, text, severity)

            monkeypatch.setattr(CopilotSetupApp, "_notify_status", _capture, raising=False)

            app = CopilotSetupApp()
            async with app.run_test() as pilot:
                app._run_plugin_upgrade("msx-mcp")
                await app.workers.wait_for_complete()
                await pilot.pause()
                assert any("copilot CLI not found on PATH" in t and sev == "error" for t, sev in statuses)

        asyncio.run(_test())


class TestPluginUninstallFlow:
    """Pilot-driven tests for the uninstall action: confirm modal + worker."""

    def test_confirm_screen_y_returns_true(self):
        async def _test():
            from textual.app import App, ComposeResult

            from copilotsetup.screens.confirm_screen import ConfirmScreen

            results: list = []

            class _Host(App):
                def compose(self) -> ComposeResult:
                    yield from ()

                def on_mount(self) -> None:
                    self.push_screen(ConfirmScreen("Delete it?"), callback=results.append)

            app = _Host()
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("y")
                await pilot.pause()
                assert results == [True]

        asyncio.run(_test())

    def test_confirm_screen_n_returns_false(self):
        async def _test():
            from textual.app import App, ComposeResult

            from copilotsetup.screens.confirm_screen import ConfirmScreen

            results: list = []

            class _Host(App):
                def compose(self) -> ComposeResult:
                    yield from ()

                def on_mount(self) -> None:
                    self.push_screen(ConfirmScreen("Delete it?"), callback=results.append)

            app = _Host()
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("n")
                await pilot.pause()
                assert results == [False]

        asyncio.run(_test())

    def test_uninstall_success_invokes_cli_and_reloads(self, monkeypatch):
        async def _test():
            import shutil as _shutil
            import subprocess as _subprocess

            calls: list[list[str]] = []

            class _OK:
                returncode = 0
                stdout = "Uninstalled msx-mcp"
                stderr = ""

            def _fake_run(cmd, **kw):
                calls.append(cmd)
                return _OK()

            monkeypatch.setattr(_shutil, "which", lambda name: "/fake/copilot")
            monkeypatch.setattr(_subprocess, "run", _fake_run)
            reloaded = []
            monkeypatch.setattr(
                CopilotSetupApp,
                "_load_state",
                lambda self: reloaded.append(True),
                raising=False,
            )

            app = CopilotSetupApp()
            async with app.run_test() as pilot:
                reloaded.clear()
                app._run_plugin_uninstall("msx-mcp")
                await app.workers.wait_for_complete()
                await pilot.pause()
                assert calls == [["/fake/copilot", "plugin", "uninstall", "msx-mcp"]]
                assert reloaded == [True]

        asyncio.run(_test())

    def test_uninstall_nonzero_exit_shows_error(self, monkeypatch):
        async def _test():
            import shutil as _shutil
            import subprocess as _subprocess

            class _Bad:
                returncode = 1
                stdout = ""
                stderr = "boom: uninstall failed\n"

            monkeypatch.setattr(_shutil, "which", lambda name: "/fake/copilot")
            monkeypatch.setattr(_subprocess, "run", lambda *a, **kw: _Bad())
            monkeypatch.setattr(CopilotSetupApp, "_load_state", lambda self: None, raising=False)

            statuses: list[tuple[str, str]] = []
            orig = CopilotSetupApp._notify_status

            def _capture(self, text, severity="information"):
                statuses.append((text, severity))
                orig(self, text, severity)

            monkeypatch.setattr(CopilotSetupApp, "_notify_status", _capture, raising=False)

            app = CopilotSetupApp()
            async with app.run_test() as pilot:
                app._run_plugin_uninstall("msx-mcp")
                await app.workers.wait_for_complete()
                await pilot.pause()
                assert any("boom: uninstall failed" in t and sev == "error" for t, sev in statuses)

        asyncio.run(_test())

    def test_uninstall_missing_copilot_binary(self, monkeypatch):
        async def _test():
            import shutil as _shutil

            monkeypatch.setattr(_shutil, "which", lambda name: None)
            monkeypatch.setattr(CopilotSetupApp, "_load_state", lambda self: None, raising=False)

            statuses: list[tuple[str, str]] = []
            orig = CopilotSetupApp._notify_status

            def _capture(self, text, severity="information"):
                statuses.append((text, severity))
                orig(self, text, severity)

            monkeypatch.setattr(CopilotSetupApp, "_notify_status", _capture, raising=False)

            app = CopilotSetupApp()
            async with app.run_test() as pilot:
                app._run_plugin_uninstall("msx-mcp")
                await app.workers.wait_for_complete()
                await pilot.pause()
                assert any("copilot CLI not found on PATH" in t and sev == "error" for t, sev in statuses)

        asyncio.run(_test())


class TestTabNavigation:
    """Left/Right arrows cycle through tabs."""

    def test_next_tab_wraps(self):
        async def _test():
            from textual.widgets import TabbedContent

            app = CopilotSetupApp()
            async with app.run_test() as pilot:
                tabs = app.query_one(TabbedContent)
                assert tabs.active == "servers"
                app.action_next_tab()
                await pilot.pause()
                assert tabs.active == "skills"
                app.action_next_tab()
                await pilot.pause()
                assert tabs.active == "plugins"
                app.action_next_tab()
                await pilot.pause()
                assert tabs.active == "lsp"
                app.action_next_tab()
                await pilot.pause()
                assert tabs.active == "sources"
                app.action_next_tab()
                await pilot.pause()
                # wrap around
                assert tabs.active == "servers"

        asyncio.run(_test())

    def test_prev_tab_wraps(self):
        async def _test():
            from textual.widgets import TabbedContent

            app = CopilotSetupApp()
            async with app.run_test() as pilot:
                tabs = app.query_one(TabbedContent)
                assert tabs.active == "servers"
                app.action_prev_tab()
                await pilot.pause()
                # wrap around to last
                assert tabs.active == "sources"
                app.action_prev_tab()
                await pilot.pause()
                assert tabs.active == "lsp"

        asyncio.run(_test())
