"""LSP servers data table widget."""

from __future__ import annotations

from textual.widgets import DataTable

from copilotsetup.state import DashboardState
from copilotsetup.widgets.status_render import reason_cell, status_cell


def populate_lsp_table(table: DataTable, state: DashboardState) -> None:
    """Fill the LSP DataTable with data from state."""
    table.clear()
    for lsp in state.lsp_servers:
        table.add_row(
            lsp.name,
            lsp.command,
            status_cell(lsp.state),
            reason_cell(lsp.reason),
            key=lsp.name,
        )
