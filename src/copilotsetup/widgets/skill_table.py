"""Skills data table widget."""

from __future__ import annotations

from textual.widgets import DataTable

from copilotsetup.state import DashboardState


def populate_skill_table(table: DataTable, state: DashboardState) -> None:
    """Fill the skills DataTable with data from state."""
    table.clear()
    for skill in state.skills:
        table.add_row(
            skill.name,
            skill.source,
            skill.status,
            key=skill.name,
        )
