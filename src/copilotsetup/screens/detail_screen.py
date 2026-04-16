"""Detail drill-down screen — shows contents of a source or plugin.

Opens when the user presses Enter on a row in the Sources or Plugins tab.
Renders sections of items in a scrollable RichLog.
"""

from __future__ import annotations

from typing import ClassVar

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import BindingType
from textual.screen import Screen
from textual.widgets import Footer, Header, RichLog, Static


class DetailScreen(Screen):
    """Screen that shows detailed contents of a source or plugin."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "dismiss_screen", "Back"),
        ("q", "dismiss_screen", "Back"),
    ]

    def __init__(self, title: str, sections: list[tuple[str, list[str]]]) -> None:
        """Create a detail screen.

        Args:
            title: Screen title (e.g. "Source: copilot-config").
            sections: List of (section_heading, items) tuples.
                      Each item is a string to display as a bullet point.
                      If items is empty, the section shows "(none)".
        """
        super().__init__()
        self._title = title
        self._sections = sections

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(f" {self._title}", id="action-title")
        yield RichLog(id="detail-log", wrap=True, markup=True)
        yield Footer()

    def on_mount(self) -> None:
        self._render_sections()

    def _render_sections(self) -> None:
        """Write all sections to the log widget."""
        log = self.query_one("#detail-log", RichLog)
        log.clear()
        for heading, items in self._sections:
            log.write(Text(""))
            log.write(f" [bold]{heading}[/bold]")
            if items:
                for item in items:
                    log.write(f"   • {item}")
            else:
                log.write("   (none)")
        log.write(Text(""))

    def update_sections(self, title: str, sections: list[tuple[str, list[str]]]) -> None:
        """Replace content with new data (called on refresh)."""
        self._title = title
        self._sections = sections
        self.query_one("#action-title", Static).update(f" {self._title}")
        self._render_sections()

    def action_dismiss_screen(self) -> None:
        self.dismiss()
