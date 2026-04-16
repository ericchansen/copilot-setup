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
        self._state: DashboardState | None = None
        self._load_state()

    @work(thread=True)
    def _load_state(self) -> None:
        """Load dashboard state in a worker thread."""
        state = load_dashboard_state()
        self.call_from_thread(self._apply_state, state)

    def _apply_state(self, state: DashboardState) -> None:
        """Apply loaded state to all tables (must run on main thread)."""
        self._state = state
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

        # If a detail screen is open, rebuild it with fresh data
        self._refresh_detail_screen()

    # -- Drill-down on Enter ----------------------------------------------------

    def _refresh_detail_screen(self) -> None:
        """If a DetailScreen is currently open, rebuild its content."""
        from copilotsetup.screens.detail_screen import DetailScreen

        if not isinstance(self.screen, DetailScreen):
            return
        # The title encodes what we're viewing: "Source: X" or "Plugin: X"
        title = self.screen._title
        if title.startswith("Source: "):
            name = title.removeprefix("Source: ")
            sections = self._build_source_sections(name)
            if sections is not None:
                self.screen.update_sections(title, sections)
        elif title.startswith("Plugin: "):
            name = title.removeprefix("Plugin: ")
            sections = self._build_plugin_sections(name)
            if sections is not None:
                self.screen.update_sections(title, sections)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Open a detail screen when Enter is pressed on a table row."""
        if self._state is None:
            return
        table_id = event.data_table.id
        row_key = str(event.row_key.value) if event.row_key else ""
        if not row_key:
            return

        if table_id == "source-table":
            self._show_source_detail(row_key)
        elif table_id == "plugin-table":
            self._show_plugin_detail(row_key)

    def _build_source_sections(self, source_name: str) -> list[tuple[str, list[str]]] | None:
        """Build detail sections for a source. Returns None if not found."""
        from copilotsetup.skills import get_skill_folders

        if self._state is None:
            return None
        src = next((s for s in self._state.raw_sources if s.name == source_name), None)
        if src is None:
            return None

        sections: list[tuple[str, list[str]]] = []

        meta = [f"Path: {src.path}", f"Exists: {'✓' if src.exists else '✗'}"]
        if src.instructions:
            meta.append(f"Instructions: ✓  ({src.instructions.name})")
        if src.portable_config:
            meta.append(f"Portable config: ✓  ({src.portable_config.name})")
        if src.lsp_servers:
            meta.append("LSP servers: ✓")
        sections.append(("Info", meta))

        server_names = sorted(src.servers.keys())
        sections.append((f"MCP Servers ({len(server_names)})", server_names))

        skill_names: list[str] = []
        for sd in src.skill_dirs:
            if sd.is_dir():
                skill_names.extend(s["name"] for s in get_skill_folders(sd))
        skill_names.sort()
        sections.append((f"Skills ({len(skill_names)})", skill_names))

        plugin_names = sorted(src.plugins.keys())
        sections.append((f"Plugins ({len(plugin_names)})", plugin_names))
        return sections

    def _show_source_detail(self, source_name: str) -> None:
        """Open detail screen for a config source."""
        from copilotsetup.screens.detail_screen import DetailScreen

        sections = self._build_source_sections(source_name)
        if sections is None:
            return
        self.push_screen(DetailScreen(f"Source: {source_name}", sections))

    def _build_plugin_sections(self, plugin_name: str) -> list[tuple[str, list[str]]] | None:
        """Build detail sections for a plugin. Returns None if not found."""
        if self._state is None:
            return None
        plugin = next((p for p in self._state.plugins if p.name == plugin_name), None)
        if plugin is None:
            return None

        sections: list[tuple[str, list[str]]] = []

        meta = [
            f"Status: {plugin.status}",
            f"Version: {plugin.version or '—'}",
            f"Source: {plugin.plugin_source or '—'}",
        ]
        if plugin.description:
            meta.append(f"Description: {plugin.description}")
        if plugin.install_path:
            meta.append(f"Install path: {plugin.install_path}")
        sections.append(("Info", meta))

        sections.append((f"Skills ({len(plugin.bundled_skills)})", plugin.bundled_skills))
        sections.append((f"MCP Servers ({len(plugin.bundled_servers)})", plugin.bundled_servers))
        if plugin.bundled_agents:
            sections.append((f"Agents ({len(plugin.bundled_agents)})", plugin.bundled_agents))
        return sections

    def _show_plugin_detail(self, plugin_name: str) -> None:
        """Open detail screen for a plugin."""
        from copilotsetup.screens.detail_screen import DetailScreen

        sections = self._build_plugin_sections(plugin_name)
        if sections is None:
            return
        self.push_screen(DetailScreen(f"Plugin: {plugin_name}", sections))

    # -- Actions --------------------------------------------------------------

    def action_run_setup(self) -> None:
        self._launch_action("Setup")

    def action_run_backup(self) -> None:
        self._launch_action("Backup")

    def action_run_restore(self) -> None:
        self._launch_action("Restore")

    def _launch_action(self, name: str) -> None:
        """Open the action screen, refresh state when it returns."""
        from copilotsetup.screens.action_screen import ActionScreen

        def _on_dismiss(refreshed: bool) -> None:
            if refreshed:
                self._load_state()

        self.push_screen(ActionScreen(name), callback=_on_dismiss)

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
