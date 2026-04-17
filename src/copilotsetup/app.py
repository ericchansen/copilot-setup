"""Copilot Setup — Textual TUI application.

Replaces the run-and-exit CLI with a persistent dashboard showing the current
state of Copilot configuration.  Lets you inspect config sources, MCP servers,
skills, plugins, and LSP servers — and trigger setup actions.
"""

from __future__ import annotations

import contextlib
from importlib.metadata import version as pkg_version
from typing import ClassVar

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
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
        Binding("left", "prev_tab", "Prev Tab", show=False, priority=True),
        Binding("right", "next_tab", "Next Tab", show=False, priority=True),
        ("f5", "run_setup", "Setup"),
        ("r", "refresh_state", "Refresh"),
        ("t", "toggle_plugin", "Enable/Disable"),
        ("u", "upgrade_plugin", "Upgrade"),
        ("x", "uninstall_plugin", "Uninstall"),
        ("q", "quit", "Quit"),
    ]

    _TAB_ORDER: ClassVar[list[str]] = ["servers", "skills", "plugins", "lsp", "sources"]

    def compose(self) -> ComposeResult:
        yield Header(icon="")
        with TabbedContent(initial="servers"):
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
                    yield _make_table(
                        "plugin",
                        ["Name", "Source", "Status", "Version", "Upgrade", "Reason"],
                    )
                yield DetailPane(id="plugin-detail")
            with TabPane("LSP", id="lsp"), Horizontal(classes="tab-layout"):
                with Vertical(classes="list-panel"):
                    yield _make_table("lsp", ["Name", "Command", "Status", "Reason"])
                yield DetailPane(id="lsp-detail")
            with TabPane("Sources", id="sources"), Horizontal(classes="tab-layout"):
                with Vertical(classes="list-panel"):
                    yield _make_table("source", ["Name", "Path", "Servers", "Skills", "Plugins", "Instructions"])
                yield DetailPane(id="source-detail")
        yield _status_bar()
        yield Footer()

    def on_mount(self) -> None:
        """Load state when the app starts."""
        self._state: DashboardState | None = None
        # Per-table tracking of which row is currently highlighted (detail pane shows it)
        self._selected_item: dict[str, str] = {}
        self._load_state()

    def on_ready(self) -> None:
        """Once the compositor is settled, make the tab bar non-focusable.

        Left/Right globally switches tabs and Up/Down always navigates rows
        in the active DataTable — one unified navigation surface is more
        intuitive than having the tab bar as a separate tab-stop.
        """
        from textual.widgets import Tabs

        for tabs in self.query(Tabs):
            tabs.can_focus = False

    @work(thread=True)
    def _load_state(self) -> None:
        """Load dashboard state in a worker thread."""
        self.call_from_thread(self._show_loading)
        state = load_dashboard_state()
        self.call_from_thread(self._apply_state, state)
        # Kick off a background upgrade check after the main state loads.
        # Runs in the same worker thread — no additional @work call needed.
        self._check_plugin_upgrades(state)

    def _check_plugin_upgrades(self, state: DashboardState) -> None:
        """Run ``git fetch`` on each git-backed plugin and surface upgrades.

        Called from inside ``_load_state``'s worker thread — safe to do blocking
        network IO here. Updates are marshalled back to the main thread.
        """
        from copilotsetup.plugin_upgrades import check_all_plugins

        def _progress(i: int, total: int, name: str) -> None:
            self.call_from_thread(self._set_status, f" checking upgrades {i}/{total} — {name}…")

        try:
            results = check_all_plugins(state.plugins, progress_cb=_progress)
        except Exception as exc:
            self.call_from_thread(self._set_status, f" ⚠ upgrade check failed: {exc}")
            return

        self.call_from_thread(self._apply_upgrade_results, results)

    def _apply_upgrade_results(self, results: list) -> None:
        """Merge upgrade check results into state and refresh the plugin table."""
        if self._state is None:
            return
        by_name = {r.name: r for r in results}
        for plugin in self._state.plugins:
            info = by_name.get(plugin.name)
            if info is None:
                continue
            plugin.upgrade_available = info.upgrade_available
            plugin.upgrade_summary = info.summary
        # Repopulate the plugin table with upgrade info + refresh summary
        try:
            populate_plugin_table(
                self.query_one("#plugin-table", DataTable),
                self._state,
            )
        except NoMatches:
            return
        try:
            ver = pkg_version("copilot-setup")
        except Exception:
            ver = "dev"
        with contextlib.suppress(NoMatches):
            status = self.query_one("#status-bar", Static)
            status.update(f" copilot-setup v{ver}  │  {self._state.summary_text}")

    def _show_loading(self) -> None:
        """Mark all tables + detail panes as loading (main thread)."""
        self._set_status(" refreshing…")
        for table in self.query(DataTable):
            table.loading = True
        for pane in self.query(DetailPane):
            pane.show_loading()

    def _set_status(self, text: str) -> None:
        """Update the status bar text (main thread)."""
        with contextlib.suppress(Exception):
            self.query_one("#status-bar", Static).update(text)

    def _apply_state(self, state: DashboardState) -> None:
        """Apply loaded state to all tables (must run on main thread)."""
        self._state = state
        try:
            populate_source_table(self.query_one("#source-table", DataTable), state)
            populate_server_table(self.query_one("#server-table", DataTable), state)
            populate_skill_table(self.query_one("#skill-table", DataTable), state)
            populate_plugin_table(
                self.query_one("#plugin-table", DataTable),
                state,
            )
            populate_lsp_table(self.query_one("#lsp-table", DataTable), state)
        except NoMatches:
            # App was torn down before the worker finished (common in tests
            # and rapid screen swaps) — nothing to populate, bail.
            return

        # Clear loading state
        for table in self.query(DataTable):
            table.loading = False

        # Update status bar
        try:
            ver = pkg_version("copilot-setup")
        except Exception:
            ver = "dev"
        with contextlib.suppress(NoMatches):
            status = self.query_one("#status-bar", Static)
            status.update(f" copilot-setup v{ver}  │  {state.summary_text}")

        # Refresh any open detail panes with fresh data, else show placeholder
        self._refresh_open_details()

        # Focus the active tab's DataTable so Up/Down work immediately
        self._focus_active_table()

    def _focus_active_table(self) -> None:
        """Move focus to the DataTable on the currently-active tab.

        NOTE for tests using ``app.run_test()`` Pilot: on cold start, focus
        sits on ``ContentTabs`` until the load worker finishes and
        ``_apply_state`` calls this method. If you press arrow keys before
        that runs, they route through the tab bar (changing the active tab),
        not the table. Always ``await pilot.pause()`` until
        ``isinstance(app.focused, DataTable)`` before asserting key bindings.
        """
        with contextlib.suppress(Exception):
            tabs = self.query_one(TabbedContent)
            active = tabs.active or self._TAB_ORDER[0]
            table = self.query_one(f"#{active.rstrip('s')}-table", DataTable)
            table.focus()

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        """When a tab is activated (mouse click, Tab key, etc.), focus its
        DataTable so Up/Down navigate rows immediately. We defer the focus
        via ``call_after_refresh`` so the event system finishes dispatching
        before we move focus — otherwise focus handling can revert the tab."""
        self.call_after_refresh(self._focus_active_table)

    # -- Detail sidebar ---------------------------------------------------------

    def _refresh_open_details(self) -> None:
        """Refresh the detail pane for each tab, showing placeholder if no row highlighted."""
        for table_id, builder_name in _TABLE_TO_BUILDER.items():
            detail_id = table_id.replace("-table", "-detail")
            try:
                pane = self.query_one(f"#{detail_id}", DetailPane)
            except Exception:
                continue
            item_key = self._selected_item.get(table_id)
            if item_key is None:
                pane.show_placeholder()
                continue
            builder = getattr(self, builder_name)
            sections = builder(item_key)
            if sections is not None:
                pane.show_detail(item_key, sections)
            else:
                pane.show_placeholder()

    def _update_detail_for_row(self, table_id: str, row_key: str) -> None:
        """Update the detail pane for a table with the given row's sections."""
        detail_id = table_id.replace("-table", "-detail")
        try:
            pane = self.query_one(f"#{detail_id}", DetailPane)
        except Exception:
            return
        builder_name = _TABLE_TO_BUILDER.get(table_id)
        if not builder_name:
            return
        builder = getattr(self, builder_name)
        sections = builder(row_key)
        if sections is None:
            pane.show_placeholder()
            return
        pane.show_detail(row_key, sections)
        self._selected_item[table_id] = row_key

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Update the detail pane as the cursor moves through rows."""
        if self._state is None:
            return
        table_id = event.data_table.id or ""
        if not table_id:
            return
        row_key = str(event.row_key.value) if event.row_key else ""
        if not row_key:
            return
        self._update_detail_for_row(table_id, row_key)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Ensure detail pane matches the activated row (Enter)."""
        if self._state is None:
            return
        table_id = event.data_table.id or ""
        row_key = str(event.row_key.value) if event.row_key else ""
        if not row_key or not table_id:
            return
        self._update_detail_for_row(table_id, row_key)

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
            f"Provided by: {skill.provided_by}",
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

    def action_prev_tab(self) -> None:
        """Switch to the previous tab (wrap-around)."""
        self._cycle_tab(-1)

    def action_next_tab(self) -> None:
        """Switch to the next tab (wrap-around)."""
        self._cycle_tab(1)

    def _cycle_tab(self, direction: int) -> None:
        """Move the active tab by `direction` steps, wrapping around."""
        try:
            tabs = self.query_one(TabbedContent)
        except Exception:
            return
        current = tabs.active or self._TAB_ORDER[0]
        if current not in self._TAB_ORDER:
            return
        idx = self._TAB_ORDER.index(current)
        new_idx = (idx + direction) % len(self._TAB_ORDER)
        new_tab = self._TAB_ORDER[new_idx]
        tabs.active = new_tab
        # Re-focus the DataTable on the new tab so Up/Down work immediately
        with contextlib.suppress(Exception):
            table = self.query_one(f"#{new_tab.rstrip('s')}-table", DataTable)
            table.focus()

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

    def action_upgrade_plugin(self) -> None:
        """Upgrade the plugin under the cursor via ``copilot plugin update``."""
        if self._state is None:
            return
        try:
            tabs = self.query_one(TabbedContent)
        except Exception:
            return
        if tabs.active != "plugins":
            self._set_status(" ⚠ Plugin upgrade only works on the Plugins tab")
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
        if not plugin.upgrade_available:
            self._set_status(f" ⚠ {name}: no upgrade available")
            return

        self._notify_status(f"⏳ upgrading {name}…")
        self._run_plugin_upgrade(plugin.name)

    @work(thread=True)
    def _run_plugin_upgrade(self, name: str) -> None:
        """Upgrade a plugin by shelling out to ``copilot plugin update <name>``.
        The Copilot CLI accepts a bare name for both direct-install and
        marketplace plugins, and handles fetch + checkout + config.json version
        update properly — we just drive it and surface output.
        """
        import shutil
        import subprocess

        copilot = shutil.which("copilot")
        if not copilot:
            self.call_from_thread(self._notify_status, f"✗ {name}: copilot CLI not found on PATH", severity="error")
            return

        self.call_from_thread(self._notify_status, f"⏳ {name}: copilot plugin update {name}…")
        try:
            proc = subprocess.run(
                [copilot, "plugin", "update", name],
                capture_output=True,
                text=True,
                timeout=180,
                check=False,
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            self.call_from_thread(self._notify_status, f"✗ {name}: upgrade error — {exc}", severity="error")
            return

        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip().splitlines()
            msg = detail[-1] if detail else f"exit {proc.returncode}"
            self.call_from_thread(self._notify_status, f"✗ {name}: {msg}", severity="error")
            return

        self.call_from_thread(self._notify_status, f"✓ {name} upgraded — reloading…")
        self.call_from_thread(self._load_state)

    def action_uninstall_plugin(self) -> None:
        """Prompt for confirmation, then uninstall the plugin under the cursor."""
        if self._state is None:
            return
        try:
            tabs = self.query_one(TabbedContent)
        except Exception:
            return
        if tabs.active != "plugins":
            self._set_status(" ⚠ Plugin uninstall only works on the Plugins tab")
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

        from copilotsetup.screens.confirm_screen import ConfirmScreen

        def _on_confirm(confirmed: bool | None) -> None:
            if confirmed:
                self._notify_status(f"⏳ uninstalling {name}…")
                self._run_plugin_uninstall(name)
            else:
                self._set_status(f" cancelled uninstall of {name}")

        self.push_screen(
            ConfirmScreen(f"Uninstall plugin '{name}'?\n\nThis runs `copilot plugin uninstall {name}`."),
            callback=_on_confirm,
        )

    @work(thread=True)
    def _run_plugin_uninstall(self, name: str) -> None:
        """Uninstall a plugin by shelling out to ``copilot plugin uninstall <name>``."""
        import shutil
        import subprocess

        copilot = shutil.which("copilot")
        if not copilot:
            self.call_from_thread(self._notify_status, f"✗ {name}: copilot CLI not found on PATH", severity="error")
            return

        self.call_from_thread(self._notify_status, f"⏳ {name}: copilot plugin uninstall {name}…")
        try:
            proc = subprocess.run(
                [copilot, "plugin", "uninstall", name],
                capture_output=True,
                text=True,
                timeout=180,
                check=False,
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            self.call_from_thread(self._notify_status, f"✗ {name}: uninstall error — {exc}", severity="error")
            return

        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip().splitlines()
            msg = detail[-1] if detail else f"exit {proc.returncode}"
            self.call_from_thread(self._notify_status, f"✗ {name}: {msg}", severity="error")
            return

        self.call_from_thread(self._notify_status, f"✓ {name} uninstalled — reloading…")
        self.call_from_thread(self._load_state)

    def _notify_status(self, text: str, severity: str = "information") -> None:
        """Update the status bar AND raise a Textual notification (toast)
        so users get persistent visible feedback during long-running actions.
        """
        self._set_status(f" {text}")
        with contextlib.suppress(Exception):
            self.notify(text, severity=severity, timeout=6.0)


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
