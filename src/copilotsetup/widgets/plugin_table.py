"""Plugins data table widget."""

from __future__ import annotations

from textual.widgets import DataTable

from copilotsetup.state import DashboardState


def populate_plugin_table(table: DataTable, state: DashboardState) -> None:
    """Fill the plugins DataTable with data from state."""
    table.clear()
    for plugin in state.plugins:
        table.add_row(
            plugin.name,
            plugin.source,
            plugin.status,
            plugin.version or "—",
            key=plugin.name,
        )
