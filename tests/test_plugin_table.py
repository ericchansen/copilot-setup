"""Tests for plugin_table populate behavior and upgrade column rendering."""

from __future__ import annotations

from textual.widgets import DataTable

from copilotsetup.state import DashboardState, PluginInfo


def _mk(name: str, installed=True, disabled=False, upgrade=False) -> PluginInfo:
    return PluginInfo(
        name=name,
        source="test",
        installed=installed,
        disabled=disabled,
        upgrade_available=upgrade,
        upgrade_summary="↑ 1" if upgrade else "",
    )


def _state(*plugins: PluginInfo) -> DashboardState:
    s = DashboardState()
    s.plugins = list(plugins)
    return s


class TestSummaryTextUpgradeCount:
    def test_upgrade_count_appears_when_nonzero(self) -> None:
        s = _state(_mk("a"), _mk("b", upgrade=True), _mk("c", upgrade=True))
        assert "3 plugins (↑ 2)" in s.summary_text

    def test_no_upgrade_suffix_when_zero(self) -> None:
        s = _state(_mk("a"), _mk("b"))
        assert "2 plugins" in s.summary_text
        assert "↑" not in s.summary_text


class TestVersionCell:
    def test_blank_version_renders_as_dash(self) -> None:
        import asyncio

        from textual.app import App, ComposeResult

        from copilotsetup.widgets.plugin_table import populate_plugin_table

        plugin = _mk("noversion")
        plugin.version = ""
        s = _state(plugin)

        class _TestApp(App):
            def compose(self) -> ComposeResult:
                table = DataTable(id="plugin-table")
                table.add_columns("Name", "Source", "Status", "Version", "Upgrade", "Reason")
                yield table

        async def _run() -> None:
            app = _TestApp()
            async with app.run_test() as pilot:
                table = app.query_one("#plugin-table", DataTable)
                populate_plugin_table(table, s)
                await pilot.pause()
                # Version column index = 3
                row = table.get_row_at(0)
                assert row[3] == "—"

        asyncio.run(_run())


class TestPopulatePluginTable:
    """Sanity-check populate function through the live app."""

    def test_row_count(self) -> None:
        import asyncio

        from textual.app import App, ComposeResult

        from copilotsetup.widgets.plugin_table import populate_plugin_table

        s = _state(_mk("a"), _mk("b", upgrade=True))

        class _TestApp(App):
            def compose(self) -> ComposeResult:
                table = DataTable(id="plugin-table")
                table.add_columns("Name", "Source", "Status", "Version", "Upgrade", "Reason")
                yield table

        async def _run() -> None:
            app = _TestApp()
            async with app.run_test() as pilot:
                table = app.query_one("#plugin-table", DataTable)
                populate_plugin_table(table, s)
                await pilot.pause()
                assert table.row_count == 2

        asyncio.run(_run())
