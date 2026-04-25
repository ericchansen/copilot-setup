"""Tests for copilotsetup.data.base — provider protocol conformance."""

from __future__ import annotations

from dataclasses import dataclass

from copilotsetup.data.base import ReadProvider, WriteProvider


@dataclass(frozen=True)
class Widget:
    name: str
    size: int


class MyReader:
    def load(self) -> list[Widget]:
        return [Widget("a", 1), Widget("b", 2)]


class MyWriter:
    def load(self) -> list[Widget]:
        return [Widget("a", 1)]

    def save(self, items: list[Widget]) -> None:
        pass


def test_reader_is_read_provider():
    assert isinstance(MyReader(), ReadProvider)


def test_writer_is_write_provider():
    assert isinstance(MyWriter(), WriteProvider)


def test_writer_is_also_read_provider():
    assert isinstance(MyWriter(), ReadProvider)


def test_reader_is_not_write_provider():
    assert not isinstance(MyReader(), WriteProvider)
