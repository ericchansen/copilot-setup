"""Tests for widget helper functions — footer_bar rendering and status_render cells."""

from __future__ import annotations

from copilotsetup.widgets.footer_bar import _render_key
from copilotsetup.widgets.status_render import reason_cell, status_cell

# ---------------------------------------------------------------------------
# FooterBar — _render_key
# ---------------------------------------------------------------------------


def test_render_key_escapes_brackets() -> None:
    """_render_key wraps the key in escaped brackets for Rich markup."""
    result = _render_key("a", "Add")
    assert "\\[a]" in result
    assert "Add" in result


def test_render_key_escapes_slash() -> None:
    """The / key renders as [/] using Rich-escaped bracket."""
    result = _render_key("/", "Filter")
    assert "\\[/]" in result
    assert "Filter" in result


def test_render_key_plain_char() -> None:
    """A plain character like 'r' appears inside brackets without extra escaping."""
    result = _render_key("r", "Refresh")
    assert "\\[r]" in result
    assert "Refresh" in result


# ---------------------------------------------------------------------------
# status_render — status_cell / reason_cell
# ---------------------------------------------------------------------------


def test_status_cell_disabled() -> None:
    cell = status_cell("disabled")
    assert str(cell) == "disabled"
    assert cell.style == "bright_black"


def test_status_cell_missing() -> None:
    cell = status_cell("missing")
    assert str(cell) == "missing"
    assert cell.style == "yellow"


def test_reason_cell_empty() -> None:
    """An empty reason string still returns a dim Text object."""
    cell = reason_cell("")
    assert str(cell) == ""
    assert cell.style == "dim"


def test_reason_cell_with_text() -> None:
    cell = reason_cell("not installed")
    assert str(cell) == "not installed"
    assert cell.style == "dim"
