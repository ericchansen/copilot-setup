"""Skills data table widget."""

from __future__ import annotations

from textual.widgets import DataTable

from copilotsetup.state import DashboardState


def populate_skill_table(table: DataTable, state: DashboardState) -> None:
    """Fill the skills DataTable with data from state, sorted by source."""
    table.clear()
    # Sort by source then name for a grouped view
    sorted_skills = sorted(state.skills, key=lambda s: (s.source, s.name))
    for skill in sorted_skills:
        table.add_row(
            skill.name,
            skill.source,
            skill.status,
            key=skill.name,
        )
