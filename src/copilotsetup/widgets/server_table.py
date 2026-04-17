"""MCP servers data table widget."""

from __future__ import annotations

from textual.widgets import DataTable

from copilotsetup.state import DashboardState
from copilotsetup.widgets.status_render import reason_cell, status_cell


def populate_server_table(table: DataTable, state: DashboardState) -> None:
    """Fill the servers DataTable with data from state."""
    table.clear()
    for srv in state.servers:
        table.add_row(
            srv.name,
            srv.source,
            srv.server_type,
            status_cell(srv.state),
            reason_cell(srv.reason),
            key=srv.name,
        )
