"""Footer bar — dynamic keybinding hints for the active tab."""

from __future__ import annotations

from textual.widgets import Static

_GLOBAL_KEYS: list[tuple[str, str]] = [
    ("/", "Filter"),
    ("r", "Refresh"),
    ("?", "Help"),
    ("q", "Quit"),
]

_ACTION_LABELS: dict[str, str] = {
    "a": "Add",
    "x": "Remove",
    "e": "Edit",
    "t": "Toggle",
    "u": "Upgrade",
    "m": "Marketplace",
    "h": "Health",
}


def _render_key(key: str, label: str) -> str:
    return f"[bold cyan]\\[{key}][/bold cyan] {label}"


class FooterBar(Static):
    """Bottom bar that updates when the active tab changes."""

    DEFAULT_CSS = """
    FooterBar {
        height: 1;
        dock: bottom;
        background: $panel;
        color: $text;
        padding: 0 1;
    }
    """

    def on_mount(self) -> None:
        self.set_actions([])

    def set_actions(self, available: list[str]) -> None:
        parts: list[str] = []
        for key in available:
            label = _ACTION_LABELS.get(key)
            if label:
                parts.append(_render_key(key, label))
        if parts:
            parts.append("[dim]│[/dim]")
        parts.extend(_render_key(k, lbl) for k, lbl in _GLOBAL_KEYS)
        self.update("  ".join(parts))
