"""Shared status rendering — colored Rich cells for health/status columns."""

from __future__ import annotations

from typing import Literal

from rich.text import Text

Status = Literal["enabled", "disabled", "missing", "broken"]

_COLORS: dict[Status, str] = {
    "enabled": "green",
    "disabled": "bright_black",
    "missing": "yellow",
    "broken": "red",
}


def status_cell(state: Status) -> Text:
    """Rich ``Text`` with the state colored appropriately."""
    return Text(state, style=_COLORS.get(state, ""))


def reason_cell(reason: str) -> Text:
    """Rich ``Text`` for the reason column (muted)."""
    return Text(reason, style="dim")
