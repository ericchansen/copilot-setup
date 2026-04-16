"""Copilot Setup — Textual TUI application.

Replaces the run-and-exit CLI with a persistent dashboard showing the current
state of Copilot configuration.  Lets you inspect config sources, MCP servers,
skills, plugins, and LSP servers — and trigger setup/backup/restore actions.
"""

from __future__ import annotations

from importlib.metadata import version as pkg_version
from typing import ClassVar

from textual import work
from textual.app import App, ComposeResult
from textual.binding import BindingType
from textual.widgets import DataTable, Footer, Header, Static, TabbedContent, TabPane

from copilotsetup.state import DashboardState, load_dashboard_state
from copilotsetup.widgets.lsp_table import populate_lsp_table
from copilotsetup.widgets.plugin_table import populate_plugin_table
from copilotsetup.widgets.server_table import populate_server_table
from copilotsetup.widgets.skill_table import populate_skill_table
from copilotsetup.widgets.source_table import populate_source_table


class CopilotSetupApp(App):
    """Textual TUI for managing GitHub Copilot CLI configuration."""

    TITLE = "Copilot Setup"
    CSS_PATH = "app.tcss"

    BINDINGS: ClassVar[list[BindingType]] = [
        ("f5", "run_setup", "Setup"),
        ("f6", "run_backup", "Backup"),
        ("f7", "run_restore", "Restore"),
        ("r", "refresh_state", "Refresh"),
        ("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent(initial="sources"):
            with TabPane("Sources", id="sources"):
                yield _make_table("source", ["Name", "Path", "Servers", "Skills", "Plugins", "Instructions"])
            with TabPane("MCP Servers", id="servers"):
                yield _make_table("server", ["Name", "Source", "Type", "Status"])
            with TabPane("Skills", id="skills"):
                yield _make_table("skill", ["Name", "Source", "Status"])
            with TabPane("Plugins", id="plugins"):
                yield _make_table("plugin", ["Name", "Source", "Status", "Version"])
            with TabPane("LSP", id="lsp"):
                yield _make_table("lsp", ["Name", "Command", "Status"])
        yield _status_bar()
        yield Footer()

    def on_mount(self) -> None:
        """Load state when the app starts."""
        self._load_state()

    @work(thread=True)
    def _load_state(self) -> None:
        """Load dashboard state in a worker thread."""
        state = load_dashboard_state()
        self.call_from_thread(self._apply_state, state)

    def _apply_state(self, state: DashboardState) -> None:
        """Apply loaded state to all tables (must run on main thread)."""
        populate_source_table(self.query_one("#source-table", DataTable), state)
        populate_server_table(self.query_one("#server-table", DataTable), state)
        populate_skill_table(self.query_one("#skill-table", DataTable), state)
        populate_plugin_table(self.query_one("#plugin-table", DataTable), state)
        populate_lsp_table(self.query_one("#lsp-table", DataTable), state)

        # Update status bar
        status = self.query_one("#status-bar", Static)
        try:
            ver = pkg_version("copilot-setup")
        except Exception:
            ver = "dev"
        status.update(f" copilot-setup v{ver}  │  {state.summary_text}")

    # -- Actions --------------------------------------------------------------

    def action_run_setup(self) -> None:
        self.notify("Setup not yet wired", severity="warning")

    def action_run_backup(self) -> None:
        self.notify("Backup not yet wired", severity="warning")

    def action_run_restore(self) -> None:
        self.notify("Restore not yet wired", severity="warning")

    def action_refresh_state(self) -> None:
        """Reload state from disk."""
        self.notify("Refreshing…")
        self._load_state()


# -- Helpers ------------------------------------------------------------------


def _make_table(name: str, columns: list[str]) -> DataTable:
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
    return Static(f" copilot-setup v{ver}  │  loading…", id="status-bar")


# -- Entry point --------------------------------------------------------------


def main() -> None:
    app = CopilotSetupApp()
    app.run()


if __name__ == "__main__":
    main()
