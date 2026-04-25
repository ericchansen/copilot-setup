"""Detail pane — Rich-formatted read-only sidebar for item details."""

from __future__ import annotations

from textual.widgets import RichLog

_EMPTY = "[dim italic]Select an item to view details[/]"


class DetailPane(RichLog):
    """Scrollable right-side panel showing Rich-formatted detail."""

    DEFAULT_CSS = """
    DetailPane {
        height: 1fr;
        border-left: tall $accent;
        padding: 0 1;
        scrollbar-size-vertical: 1;
    }
    """

    def on_mount(self) -> None:
        self.wrap = True
        self.markup = True
        self.set_content(_EMPTY)

    def set_content(self, text: str) -> None:
        """Replace all content with *text* (Rich markup supported)."""
        self.clear()
        self.write(text)

    def show_empty(self) -> None:
        """Reset to the default placeholder."""
        self.set_content(_EMPTY)
