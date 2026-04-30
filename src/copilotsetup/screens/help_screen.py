"""Full-screen keybinding help overlay."""

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Center, Middle
from textual.screen import ModalScreen
from textual.widgets import Static

_HELP_CONTENT = """\
[bold]Copilot Setup — Keyboard Shortcuts[/bold]

[bold underline]Navigation[/bold underline]
  ←/→          Switch tabs
  ↑/↓          Navigate rows
  /             Filter rows

[bold underline]Global[/bold underline]
  r             Refresh data
  ?             This help screen
  q             Quit

[bold underline]MCP Servers tab[/bold underline]
  a             Add server
  x             Remove server
  h             Probe server health

[bold underline]Plugins tab[/bold underline]
  a             Install plugin
  x             Uninstall plugin
  t             Enable / Disable
  u             Upgrade plugin
  m             Go to Marketplaces tab

[bold underline]Settings tab[/bold underline]
  e             Edit setting

[bold underline]Marketplaces tab[/bold underline]
  a             Add marketplace
  x             Remove marketplace
  u             Update marketplace catalog(s)
  m             Browse selected marketplace

[bold underline]Profiles tab[/bold underline]
  a             Create profile (clone from root)
  e             Rename profile
  x             Delete profile
  t             Browse profile (view/edit its config across all tabs)
"""


class HelpScreen(ModalScreen[None]):
    """Modal help overlay — press ? or Escape to close."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("question_mark", "dismiss_help", "Close", show=False),
        Binding("escape", "dismiss_help", "Close", show=False),
    ]

    DEFAULT_CSS = """
    HelpScreen {
        align: center middle;
    }
    #help-box {
        width: 60;
        max-height: 80%;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    """

    def compose(self) -> ComposeResult:
        with Center(), Middle():
            yield Static(_HELP_CONTENT, id="help-box", markup=True)

    def action_dismiss_help(self) -> None:
        self.dismiss(None)
