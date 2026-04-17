"""Generic Yes/No confirmation modal.

Used for destructive actions (e.g. plugin uninstall). Press ``y`` to accept,
``n`` / ``escape`` to cancel. Returns ``True`` only on explicit ``y``.
"""

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static


class ConfirmScreen(ModalScreen[bool]):
    """Yes/No confirmation modal. Dismisses with ``True`` on ``y``, else ``False``."""

    DEFAULT_CSS = """
    ConfirmScreen {
        align: center middle;
    }
    ConfirmScreen > Vertical {
        background: $panel;
        border: thick $warning;
        padding: 1 2;
        width: 60;
        height: auto;
        min-height: 7;
    }
    #confirm-prompt {
        width: 100%;
        height: auto;
        padding-bottom: 1;
    }
    #confirm-help {
        width: 100%;
        height: auto;
        color: $text-muted;
    }
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        ("y", "accept", "Yes"),
        ("n", "cancel", "No"),
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(self, prompt: str) -> None:
        super().__init__()
        self._prompt = prompt

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(self._prompt, id="confirm-prompt")
            yield Static("\\[y] Yes    \\[n] No    \\[Esc] Cancel", id="confirm-help")

    def action_accept(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)
