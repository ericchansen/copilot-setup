"""Plugins data table widget."""

from __future__ import annotations

from rich.text import Text
from textual.widgets import DataTable

from copilotsetup.state import DashboardState
from copilotsetup.widgets.status_render import reason_cell, status_cell


def populate_plugin_table(
    table: DataTable,
    state: DashboardState,
) -> None:
    """Fill the plugins DataTable with data from state."""
    table.clear()
    for plugin in state.plugins:
        upgrade_cell = Text(plugin.upgrade_summary, style="green") if plugin.upgrade_available else Text("")
        table.add_row(
            plugin.name,
            plugin.source,
            status_cell(plugin.state),
            plugin.version or "—",
            upgrade_cell,
            reason_cell(plugin.reason),
            key=plugin.name,
        )
