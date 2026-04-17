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
                # All hidden by default
                for pane in panes:
                    assert not pane.is_visible

        asyncio.run(_test())
