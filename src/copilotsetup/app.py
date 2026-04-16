"""Copilot Setup — Textual TUI application.

Replaces the run-and-exit CLI with a persistent dashboard showing the current
state of Copilot configuration.  Lets you inspect config sources, MCP servers,
skills, plugins, and LSP servers — and trigger setup/backup/restore actions.
"""

from __future__ import annotations

from importlib.metadata import version as pkg_version
from typing import ClassVar

from textual.app import App, ComposeResult
from textual.binding import BindingType
from textual.widgets import DataTable, Footer, Header, Static, TabbedContent, TabPane


class CopilotSetupApp(App):
    """Textual TUI for managing GitHub Copilot CLI configuration."""

    TITLE = "Copilot Setup"
    CSS_PATH = "app.tcss"

    BINDINGS: ClassVar[list[BindingType]] = [
        ("f5", "run_setup", "Setup"),
        ("f6", "run_backup", "Backup"),
        ("f7", "run_restore", "Restore"),
        ("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent(initial="sources"):
            with TabPane("Sources", id="sources"):
                yield _placeholder_table("source", ["Name", "Path", "Servers", "Skills", "Plugins", "Instructions"])
            with TabPane("MCP Servers", id="servers"):
                yield _placeholder_table("server", ["Name", "Source", "Type", "Status"])
            with TabPane("Skills", id="skills"):
                yield _placeholder_table("skill", ["Name", "Source", "Status"])
            with TabPane("Plugins", id="plugins"):
                yield _placeholder_table("plugin", ["Name", "Source", "Status", "Version"])
            with TabPane("LSP", id="lsp"):
                yield _placeholder_table("lsp", ["Name", "Command", "Status"])
        yield _status_bar()
        yield Footer()

    # -- Actions (stubs for now) ------------------------------------------

    def action_run_setup(self) -> None:
        self.notify("Setup not yet wired", severity="warning")

    def action_run_backup(self) -> None:
        self.notify("Backup not yet wired", severity="warning")

    def action_run_restore(self) -> None:
        self.notify("Restore not yet wired", severity="warning")


# -- Helpers --------------------------------------------------------------


def _placeholder_table(name: str, columns: list[str]) -> DataTable:
    """Create a DataTable with column headers but no rows."""
    table = DataTable(id=f"{name}-table", zebra_stripes=True)
    table.cursor_type = "row"
    for col in columns:
        table.add_column(col, key=col.lower())
    return table


def _status_bar() -> Static:
    try:
        ver = pkg_version("copilot-setup")
    except Exception:
        ver = "dev"
    return Static(f" copilot-setup v{ver}", id="status-bar")


# -- Entry point ----------------------------------------------------------


def main() -> None:
    app = CopilotSetupApp()
    app.run()


if __name__ == "__main__":
    main()
