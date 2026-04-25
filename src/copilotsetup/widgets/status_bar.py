"""Status bar — app version, tab counts, health summary, progress."""

from __future__ import annotations

from textual.widgets import Static

from copilotsetup.config import APP_NAME, APP_VERSION


class StatusBar(Static):
    """Bottom status bar aggregating information from all tabs."""

    DEFAULT_CSS = """
    StatusBar {
        height: 1;
        dock: bottom;
        background: $surface;
        color: $text-muted;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self._counts: dict[str, int] = {}
        self._health: str = ""
        self._progress: str = ""

    def on_mount(self) -> None:
        self._refresh()

    def set_counts(self, counts: dict[str, int]) -> None:
        self._counts = dict(counts)
        self._refresh()

    def set_health(self, summary: str) -> None:
        self._health = summary
        self._refresh()

    def set_progress(self, text: str) -> None:
        self._progress = text
        self._refresh()

    def clear_progress(self) -> None:
        self._progress = ""
        self._refresh()

    def _refresh(self) -> None:
        parts: list[str] = [f"{APP_NAME} v{APP_VERSION}"]
        if self._counts:
            count_parts = [f"{v} {k}" for k, v in self._counts.items() if v]
            if count_parts:
                parts.append(" | ".join(count_parts))
        if self._health:
            parts.append(self._health)
        if self._progress:
            parts.append(f"[italic]{self._progress}[/italic]")
        self.update(" │ ".join(parts))
