"""Inline filter bar — hidden by default, toggled by ``/``."""

from __future__ import annotations

from typing import ClassVar

from textual import on
from textual.binding import Binding
from textual.message import Message
from textual.widgets import Input


class FilterInput(Input):
    """Search/filter input that emits ``Updated`` and ``Cleared`` messages."""

    DEFAULT_CSS = """
    FilterInput {
        display: none;
        height: 1;
        dock: top;
        border: none;
        padding: 0 1;
        background: $boost;
    }
    FilterInput:focus { border: none; }
    FilterInput.-visible { display: block; }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "clear_filter", "Clear filter", show=False),
    ]

    class Cleared(Message):
        """Sent when the filter is dismissed."""

    class Updated(Message):
        """Sent when the filter text changes."""

        def __init__(self, query: str) -> None:
            self.query = query
            super().__init__()

    def __init__(self, **kwargs: object) -> None:
        super().__init__(placeholder="Filter…", **kwargs)  # type: ignore[arg-type]

    def show(self) -> None:
        self.add_class("-visible")
        self.focus()

    def hide(self) -> None:
        self.value = ""
        self.remove_class("-visible")
        self.post_message(self.Cleared())

    @on(Input.Changed)
    def _on_text_changed(self, event: Input.Changed) -> None:
        event.stop()
        self.post_message(self.Updated(self.value))

    def action_clear_filter(self) -> None:
        self.hide()
