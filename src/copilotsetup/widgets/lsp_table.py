"""LSP servers data table widget."""

from __future__ import annotations

from textual.widgets import DataTable

from copilotsetup.state import DashboardState


def populate_lsp_table(table: DataTable, state: DashboardState) -> None:
    """Fill the LSP DataTable with data from state."""
    table.clear()
    for lsp in state.lsp_servers:
        table.add_row(
            lsp.name,
            lsp.command,
            lsp.status,
            key=lsp.name,
        )
