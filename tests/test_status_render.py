"""Tests for copilotsetup.widgets.status_render — status/reason Rich cells."""

from __future__ import annotations

from copilotsetup.widgets.status_render import reason_cell, status_cell


def test_status_cell_enabled():
    cell = status_cell("enabled")
    assert str(cell) == "enabled"
    assert cell.style == "green"


def test_status_cell_broken():
    cell = status_cell("broken")
    assert str(cell) == "broken"
    assert cell.style == "red"


def test_reason_cell():
    cell = reason_cell("some reason")
    assert str(cell) == "some reason"
    assert cell.style == "dim"
