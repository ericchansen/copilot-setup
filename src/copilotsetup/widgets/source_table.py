"""Config sources data table widget."""

from __future__ import annotations

from textual.widgets import DataTable

from copilotsetup.state import DashboardState


def populate_source_table(table: DataTable, state: DashboardState) -> None:
    """Fill the sources DataTable with data from state."""
    table.clear()
    for src in state.sources:
        table.add_row(
            f"{'✓' if src.exists else '✗'} {src.name}",
            str(src.path),
            str(src.server_count),
            str(src.skill_count),
            str(src.plugin_count),
            "✓" if src.has_instructions else "—",
            key=src.name,
        )
