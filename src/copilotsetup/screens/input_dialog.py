"""Simple input dialog screen for collecting a single text value."""

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Center, Middle, Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label


class InputDialog(ModalScreen[str | None]):
    """Modal dialog that prompts for a text value.

    Returns the entered string on submit, or ``None`` on cancel/escape.
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    DEFAULT_CSS = """
    InputDialog {
        align: center middle;
    }
    #input-box {
        width: 50;
        max-height: 10;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    #input-label {
        margin-bottom: 1;
    }
    """

    def __init__(
        self,
        prompt: str = "Enter a value:",
        default: str = "",
        placeholder: str = "",
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self._prompt = prompt
        self._default = default
        self._placeholder = placeholder

    def compose(self) -> ComposeResult:
        with Center(), Middle(), Vertical(id="input-box"):
            yield Label(self._prompt, id="input-label")
            yield Input(
                value=self._default,
                placeholder=self._placeholder or "type and press Enter",
                id="input-field",
            )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        self.dismiss(value if value else None)

    def action_cancel(self) -> None:
        self.dismiss(None)
