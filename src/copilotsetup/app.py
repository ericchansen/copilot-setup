"""Copilot Setup — Textual TUI application.

Replaces the run-and-exit CLI with a persistent dashboard showing the current
state of Copilot configuration.  Lets you inspect config sources, MCP servers,
skills, plugins, and LSP servers — and trigger setup/backup/restore actions.
"""

from __future__ import annotations

import contextlib
from importlib.metadata import version as pkg_version
from typing import ClassVar

from textual import work
from textual.app import App, ComposeResult
from textual.binding import BindingType
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Footer, Header, Static, TabbedContent, TabPane

from copilotsetup.state import DashboardState, load_dashboard_state
from copilotsetup.widgets.detail_pane import DetailPane
from copilotsetup.widgets.lsp_table import populate_lsp_table
from copilotsetup.widgets.plugin_table import populate_plugin_table
from copilotsetup.widgets.server_table import populate_server_table
from copilotsetup.widgets.skill_table import populate_skill_table
from copilotsetup.widgets.source_table import populate_source_table

# Maps table IDs to their detail builder method names
_TABLE_TO_BUILDER: dict[str, str] = {
    "source-table": "_build_source_sections",
    "server-table": "_build_server_sections",
    "skill-table": "_build_skill_sections",
    "plugin-table": "_build_plugin_sections",
    "lsp-table": "_build_lsp_sections",
}


class CopilotSetupApp(App):
    """Textual TUI for managing GitHub Copilot CLI configuration."""

    TITLE = "Copilot Setup"
    CSS_PATH = "app.tcss"

    BINDINGS: ClassVar[list[BindingType]] = [
        ("f5", "run_setup", "Setup"),
        ("f6", "run_backup", "Backup"),
        ("f7", "run_restore", "Restore"),
        ("r", "refresh_state", "Refresh"),
        ("t", "toggle_plugin", "Enable/Disable"),
        ("escape", "hide_detail", "Close"),
        ("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(icon="")
        with TabbedContent(initial="sources"):
            with TabPane("Sources", id="sources"), Horizontal(classes="tab-layout"):
                with Vertical(classes="list-panel"):
                    yield _make_table("source", ["Name", "Path", "Servers", "Skills", "Plugins", "Instructions"])
                yield DetailPane(id="source-detail")
            with TabPane("MCP Servers", id="servers"), Horizontal(classes="tab-layout"):
                with Vertical(classes="list-panel"):
                    yield _make_table("server", ["Name", "Source", "Type", "Status", "Reason"])
                yield DetailPane(id="server-detail")
            with TabPane("Skills", id="skills"), Horizontal(classes="tab-layout"):
                with Vertical(classes="list-panel"):
                    yield _make_table("skill", ["Name", "Source", "Status", "Reason"])
                yield DetailPane(id="skill-detail")
            with TabPane("Plugins", id="plugins"), Horizontal(classes="tab-layout"):
                with Vertical(classes="list-panel"):
                    yield _make_table("plugin", ["Name", "Source", "Status", "Version", "Reason"])
                yield DetailPane(id="plugin-detail")
            with TabPane("LSP", id="lsp"), Horizontal(classes="tab-layout"):
                with Vertical(classes="list-panel"):
                    yield _make_table("lsp", ["Name", "Command", "Status", "Reason"])
                yield DetailPane(id="lsp-detail")
        yield _status_bar()
        yield Footer()

    def on_mount(self) -> None:
        """Load state when the app starts."""
        self._state: DashboardState | None = None
        # Per-table tracking of which item has the detail pane open
        self._selected_item: dict[str, str] = {}
        self._load_state()

    @work(thread=True)
    def _load_state(self) -> None:
        """Load dashboard state in a worker thread."""
        self.call_from_thread(self._set_status, " refreshing…")
        state = load_dashboard_state()
        self.call_from_thread(self._apply_state, state)

    def _set_status(self, text: str) -> None:
        """Update the status bar text (main thread)."""
        with contextlib.suppress(Exception):
            self.query_one("#status-bar", Static).update(text)

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

        # Refresh any open detail panes with fresh data
        self._refresh_open_details()

    # -- Detail sidebar ---------------------------------------------------------

    def _refresh_open_details(self) -> None:
        """Refresh any detail panes that are currently visible."""
        for table_id, item_key in list(self._selected_item.items()):
            builder_name = _TABLE_TO_BUILDER.get(table_id)
            if not builder_name:
                continue
            builder = getattr(self, builder_name)
            sections = builder(item_key)
            if sections is not None:
                detail_id = table_id.replace("-table", "-detail")
                pane = self.query_one(f"#{detail_id}", DetailPane)
                if pane.is_visible:
                    pane.show_detail(item_key, sections)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Toggle the detail sidebar when Enter is pressed on a table row."""
        if self._state is None:
            return
        table_id = event.data_table.id or ""
        row_key = str(event.row_key.value) if event.row_key else ""
        if not row_key or not table_id:
            return

        # Find the detail pane sibling
        detail_id = table_id.replace("-table", "-detail")
        try:
            pane = self.query_one(f"#{detail_id}", DetailPane)
        except Exception:
            return

        # Toggle: same item → hide, different item → show new
        if self._selected_item.get(table_id) == row_key and pane.is_visible:
            pane.hide_detail()
            self._selected_item.pop(table_id, None)
            return

        # Build sections for this item
        builder_name = _TABLE_TO_BUILDER.get(table_id)
        if not builder_name:
            return
        builder = getattr(self, builder_name)
        sections = builder(row_key)
        if sections is None:
            return

        pane.show_detail(row_key, sections)
        self._selected_item[table_id] = row_key

    def action_hide_detail(self) -> None:
        """Hide the detail pane in the active tab."""
        for pane in self.query(DetailPane):
            if pane.is_visible:
                pane.hide_detail()
        # Clear selection tracking
        for table_id in list(self._selected_item.keys()):
            detail_id = table_id.replace("-table", "-detail")
            try:
                p = self.query_one(f"#{detail_id}", DetailPane)
                if not p.is_visible:
                    self._selected_item.pop(table_id, None)
            except Exception:
                pass

    # -- Section builders -------------------------------------------------------

    def _build_source_sections(self, source_name: str) -> list[tuple[str, list[str]]] | None:
        """Build detail sections for a source."""
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

    def _build_server_sections(self, server_name: str) -> list[tuple[str, list[str]]] | None:
        """Build detail sections for an MCP server."""
        if self._state is None:
            return None
        srv = next((s for s in self._state.servers if s.name == server_name), None)
        if srv is None:
            return None

        meta = [
            f"Source: {srv.source}",
            f"Type: {srv.server_type}",
            f"Status: {srv.state}",
        ]
        if srv.reason:
            meta.append(f"Reason: {srv.reason}")
        if srv.server_type == "http" and srv.oauth_status in ("authenticated", "needs_auth"):
            oauth_label = {
                "authenticated": "✓ Authenticated",
                "needs_auth": "⚠ Needs OAuth",
            }[srv.oauth_status]
            meta.append(f"OAuth: {oauth_label}")
        if not srv.env_ok:
            meta.append("⚠ Environment variables missing")
        if srv.built:
            meta.append("Built: ✓")
        return [("Info", meta)]

    def _build_skill_sections(self, skill_name: str) -> list[tuple[str, list[str]]] | None:
        """Build detail sections for a skill."""
        if self._state is None:
            return None
        skill = next((s for s in self._state.skills if s.name == skill_name), None)
        if skill is None:
            return None

        meta = [
            f"Source: {skill.source}",
            f"Status: {skill.state}",
            f"Linked: {'✓' if skill.is_linked else '✗'}",
        ]
        if skill.reason:
            meta.append(f"Reason: {skill.reason}")
        if skill.link_target:
            meta.append(f"Link target: {skill.link_target}")
        if not skill.link_ok and skill.is_linked:
            meta.append("⚠ Link is broken")
        return [("Info", meta)]

    def _build_plugin_sections(self, plugin_name: str) -> list[tuple[str, list[str]]] | None:
        """Build detail sections for a plugin."""
        if self._state is None:
            return None
        plugin = next((p for p in self._state.plugins if p.name == plugin_name), None)
        if plugin is None:
            return None

        sections: list[tuple[str, list[str]]] = []

        meta = [
            f"Status: {plugin.state}",
            f"Version: {plugin.version or '—'}",
            f"Source: {plugin.plugin_source or '—'}",
        ]
        if plugin.reason:
            meta.append(f"Reason: {plugin.reason}")
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

    def _build_lsp_sections(self, lsp_name: str) -> list[tuple[str, list[str]]] | None:
        """Build detail sections for an LSP server."""
        if self._state is None:
            return None
        lsp = next((s for s in self._state.lsp_servers if s.name == lsp_name), None)
        if lsp is None:
            return None

        meta = [
            f"Command: {lsp.command}",
            f"Status: {lsp.state}",
            f"Binary found: {'✓' if lsp.binary_ok else '✗'}",
        ]
        if lsp.reason:
            meta.append(f"Reason: {lsp.reason}")
        return [("Info", meta)]

    # -- Column sorting ---------------------------------------------------------

    def on_data_table_header_selected(self, event: DataTable.HeaderSelected) -> None:
        """Sort by clicked column header (toggle asc/desc)."""
        table = event.data_table
        table_id = table.id or ""
        col_key = str(event.column_key.value) if hasattr(event.column_key, "value") else str(event.column_key)

        if not hasattr(self, "_sort_state"):
            self._sort_state: dict[str, tuple[str, bool]] = {}

        prev = self._sort_state.get(table_id)
        reverse = not prev[1] if prev and prev[0] == col_key else False

        self._sort_state[table_id] = (col_key, reverse)
        table.sort(event.column_key, reverse=reverse)

    # -- Actions ----------------------------------------------------------------

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
        self._load_state()

    def action_toggle_plugin(self) -> None:
        """Toggle enabled/disabled for the plugin under the cursor.

        Only active on the Plugins tab. Updates ~/.copilot/config.json and
        refreshes state.
        """
        if self._state is None:
            return
        try:
            tabs = self.query_one(TabbedContent)
        except Exception:
            return
        if tabs.active != "plugins":
            self._set_status(" ⚠ Plugin toggle only works on the Plugins tab")
            return

        table = self.query_one("#plugin-table", DataTable)
        if table.cursor_row < 0 or not table.row_count:
            return
        try:
            row_key = table.coordinate_to_cell_key((table.cursor_row, 0)).row_key
        except Exception:
            return
        name = str(row_key.value) if row_key else ""
        if not name:
            return

        plugin = next((p for p in self._state.plugins if p.name == name), None)
        if plugin is None:
            return
        if not plugin.installed:
            self._set_status(f" ⚠ {name} is not installed")
            return

        from copilotsetup.state import set_plugin_enabled

        new_enabled = plugin.disabled  # flip
        ok = set_plugin_enabled(name, new_enabled)
        if not ok:
            self._set_status(f" ✗ Failed to toggle {name}")
            return
        action = "enabled" if new_enabled else "disabled"
        self._set_status(f" ✓ {name} {action} — reloading…")
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


_HELP_TEXT = """copilot-setup — manage GitHub Copilot CLI configuration

Usage:
  copilot-setup              Launch the interactive TUI dashboard.
  copilot-setup doctor       Probe all configured MCP servers and report health.
  copilot-setup update       Show whether config-source repos have new commits.
  copilot-setup update --apply
                             Fast-forward pull each config-source repo.
  copilot-setup --help       Show this message.
  copilot-setup --version    Print the installed version.

See `llm.txt` at the repo root for a machine-readable reference.
"""


def main() -> None:
    import sys

    argv = sys.argv[1:]
    if argv and argv[0] in {"-h", "--help", "help"}:
        print(_HELP_TEXT)
        raise SystemExit(0)

    if argv and argv[0] in {"-V", "--version"}:
        try:
            print(pkg_version("copilot-setup"))
        except Exception:
            print("unknown")
        raise SystemExit(0)

    if argv and argv[0] == "update":
        from copilotsetup.update_sources import run_cli as update_cli

        apply = "--apply" in argv[1:]
        raise SystemExit(update_cli(apply=apply))

    if argv and argv[0] == "doctor":
        from copilotsetup.doctor import run_cli as doctor_cli

        raise SystemExit(doctor_cli())

    app = CopilotSetupApp()
    app.run()


if __name__ == "__main__":
    main()
