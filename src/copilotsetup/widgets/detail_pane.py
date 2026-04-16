"""Inline detail pane — shows contents of a selected row.

Renders inside a TabPane as a collapsible right-hand sidebar.
Replaces the old full-screen DetailScreen approach.
"""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import RichLog, Static


class DetailPane(Vertical):
    """Collapsible detail sidebar for drill-down views."""

    DEFAULT_CSS = """
    DetailPane {
        width: 40%;
        display: none;
        border-left: thick $primary;
        padding: 1 1 0 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("", id="detail-title", classes="detail-title")
        yield RichLog(id="detail-log", wrap=True, markup=True)

    def show_detail(self, title: str, sections: list[tuple[str, list[str]]]) -> None:
        """Show the pane with the given content."""
        self.query_one("#detail-title", Static).update(f" {title}")
        self._render_sections(sections)
        self.display = True

    def hide_detail(self) -> None:
        """Hide the pane and clear content."""
        self.display = False
        self.query_one("#detail-log", RichLog).clear()

    @property
    def is_visible(self) -> bool:
        return self.display

    def _render_sections(self, sections: list[tuple[str, list[str]]]) -> None:
        """Write all sections to the log widget."""
        log = self.query_one("#detail-log", RichLog)
        log.clear()
        for heading, items in sections:
            log.write(Text(""))
            log.write(f" [bold]{heading}[/bold]")
            if items:
                for item in items:
                    log.write(f"   • {item}")
            else:
                log.write("   (none)")
        log.write(Text(""))
