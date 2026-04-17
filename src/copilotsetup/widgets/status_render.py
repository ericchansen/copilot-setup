"""Shared status rendering helpers — unified 4-state vocabulary."""

from __future__ import annotations

from rich.text import Text

from copilotsetup.state import Status

# Terminal-friendly colors for each state.
_STATE_COLORS: dict[Status, str] = {
    "enabled": "green",
    "disabled": "bright_black",
    "missing": "yellow",
    "broken": "red",
}


def status_cell(state: Status) -> Text:
    """Return a Rich ``Text`` object with the state colored appropriately."""
    return Text(state, style=_STATE_COLORS.get(state, ""))


def reason_cell(reason: str) -> Text:
    """Return a Rich ``Text`` object for the reason column (muted)."""
    return Text(reason, style="dim")
