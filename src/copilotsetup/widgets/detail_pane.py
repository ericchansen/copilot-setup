"""Always-visible detail pane — shows contents of the highlighted row.

Renders inside a TabPane as a permanent right-hand sidebar (winget-tui style).
When no row is highlighted, shows a "Select a row" placeholder.
"""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import RichLog, Static

_PLACEHOLDER = "[dim]Select a row to see details[/dim]"
_LOADING = "[dim]Loading…[/dim]"


class DetailPane(Vertical):
    """Always-visible detail sidebar for drill-down views."""

    DEFAULT_CSS = """
    DetailPane {
        width: 40%;
        border-left: thick $primary;
        padding: 1 1 0 1;
    }
    """

    def on_mount(self) -> None:
        """Show placeholder initially."""
        self.query_one("#detail-title", Static).update(" Details")
        log = self.query_one("#detail-log", RichLog)
        log.write(_PLACEHOLDER)

    def compose(self) -> ComposeResult:
        yield Static("", id="detail-title", classes="detail-title")
        yield RichLog(id="detail-log", wrap=True, markup=True)

    def show_detail(self, title: str, sections: list[tuple[str, list[str]]]) -> None:
        """Replace contents with the given title + sections."""
        self.query_one("#detail-title", Static).update(f" {title}")
        self._render_sections(sections)

    def show_loading(self) -> None:
        """Display a loading placeholder."""
        self.query_one("#detail-title", Static).update(" Details")
        log = self.query_one("#detail-log", RichLog)
        log.clear()
        log.write(_LOADING)

    def show_placeholder(self) -> None:
        """Display the 'Select a row' placeholder."""
        self.query_one("#detail-title", Static).update(" Details")
        log = self.query_one("#detail-log", RichLog)
        log.clear()
        log.write(_PLACEHOLDER)

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
