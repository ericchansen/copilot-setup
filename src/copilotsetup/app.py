"""copilot-setup — Textual TUI for managing GitHub Copilot CLI configuration.

The app composes a tabbed dashboard from a registry of BaseTab subclasses.
Adding a new tab requires only a tab class + an entry in ``_TAB_DEFINITIONS``.
"""

from __future__ import annotations

import os
import sys
from contextlib import suppress
from typing import ClassVar

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Header, TabbedContent, TabPane

from copilotsetup.config import APP_NAME, APP_VERSION
from copilotsetup.tabs.agents import AgentsTab
from copilotsetup.tabs.base import BaseTab
from copilotsetup.tabs.environment import EnvironmentTab
from copilotsetup.tabs.extensions import ExtensionsTab
from copilotsetup.tabs.hooks import HooksTab
from copilotsetup.tabs.lsp_servers import LspServersTab
from copilotsetup.tabs.marketplaces import MarketplacesTab
from copilotsetup.tabs.mcp_servers import McpServersTab
from copilotsetup.tabs.permissions import PermissionsTab
from copilotsetup.tabs.plugins import PluginsTab
from copilotsetup.tabs.profiles import ProfilesTab
from copilotsetup.tabs.settings import SettingsTab
from copilotsetup.tabs.skills import SkillsTab
from copilotsetup.widgets.footer_bar import FooterBar
from copilotsetup.widgets.status_bar import StatusBar

# ── Tab registry ─────────────────────────────────────────────────────────────
# (label, pane-id, tab-class)
# To add a tab: import the class and add an entry here. That's it.

_TAB_DEFINITIONS: list[tuple[str, str, type[BaseTab]]] = [
    ("Plugins", "tab-plugins", PluginsTab),
    ("MCP Servers", "tab-mcp-servers", McpServersTab),
    ("Skills", "tab-skills", SkillsTab),
    ("Agents", "tab-agents", AgentsTab),
    ("LSP Servers", "tab-lsp-servers", LspServersTab),
    ("Extensions", "tab-extensions", ExtensionsTab),
    ("Hooks", "tab-hooks", HooksTab),
    ("Permissions", "tab-permissions", PermissionsTab),
    ("Profiles", "tab-profiles", ProfilesTab),
    ("Environment", "tab-environment", EnvironmentTab),
    ("Settings", "tab-settings", SettingsTab),
    ("Marketplaces", "tab-marketplaces", MarketplacesTab),
]


class CopilotSetupApp(App[None]):
    """TUI for viewing and managing GitHub Copilot CLI configuration."""

    TITLE = f"{APP_NAME} v{APP_VERSION}"
    CSS_PATH = "app.tcss"

    # Original COPILOT_HOME before any profile browsing
    _original_copilot_home: str | None = None
    _browsing_profile: str = ""

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("left", "prev_tab", "Prev Tab", show=False, priority=True),
        Binding("right", "next_tab", "Next Tab", show=False, priority=True),
        Binding("q", "quit", "Quit", priority=True),
        Binding("question_mark", "help", "Help", key_display="?"),
        Binding("slash", "filter", "Filter", key_display="/"),
        Binding("r", "refresh", "Refresh"),
        # Action keys — forwarded to the active tab
        Binding("a", "tab_action('a')", "Add", show=False),
        Binding("x", "tab_action('x')", "Remove", show=False),
        Binding("e", "tab_action('e')", "Edit", show=False),
        Binding("t", "tab_action('t')", "Toggle", show=False),
        Binding("u", "tab_action('u')", "Upgrade", show=False),
        Binding("m", "tab_action('m')", "Marketplace", show=False),
        Binding("h", "tab_action('h')", "Health", show=False),
        Binding("s", "tab_action('s')", "Save", show=False),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False, icon="")
        with TabbedContent():
            for label, pane_id, tab_cls in _TAB_DEFINITIONS:
                with TabPane(label, id=pane_id):
                    yield tab_cls(tab_label=label, id=f"content-{pane_id}")
        yield StatusBar(id="status-bar")
        yield FooterBar(id="footer-bar")

    def on_ready(self) -> None:
        """Make the tab bar non-focusable.

        Left/Right globally switches tabs and Up/Down always navigates rows
        in the active DataTable — one unified navigation surface.
        """
        from textual.widgets import Tabs

        for tabs in self.query(Tabs):
            tabs.can_focus = False

        from copilotsetup.data.profiles import detect_active_profile

        profile = detect_active_profile()
        if profile:
            with suppress(Exception):
                self.query_one("#status-bar", StatusBar).set_profile(profile)

    # --- tab events -----------------------------------------------------------

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        active = self._active_tab()
        if active is not None:
            self.query_one("#footer-bar", FooterBar).set_actions(active.available_actions)

    def on_base_tab_tab_activated(self, event: BaseTab.TabActivated) -> None:
        self.query_one("#footer-bar", FooterBar).set_actions(event.available_actions)

    def on_base_tab_data_loaded(self, event: BaseTab.DataLoaded) -> None:
        self._update_counts()

    # --- global actions -------------------------------------------------------

    def action_help(self) -> None:
        from copilotsetup.screens.help_screen import HelpScreen

        self.push_screen(HelpScreen())

    def action_prev_tab(self) -> None:
        """Switch to the previous tab (wrap-around)."""
        self._cycle_tab(-1)

    def action_next_tab(self) -> None:
        """Switch to the next tab (wrap-around)."""
        self._cycle_tab(1)

    def _cycle_tab(self, direction: int) -> None:
        """Move the active tab by ``direction`` steps, wrapping around."""
        try:
            tc = self.query_one(TabbedContent)
        except Exception:
            return
        pane_ids = [pid for _, pid, _ in _TAB_DEFINITIONS]
        current = tc.active
        if current not in pane_ids:
            return
        idx = pane_ids.index(current)
        new_idx = (idx + direction) % len(pane_ids)
        tc.active = pane_ids[new_idx]
        # Re-focus the DataTable on the new tab so Up/Down work immediately
        with suppress(Exception):
            tab = self.query_one(f"#content-{pane_ids[new_idx]}", BaseTab)
            tab.focus_table()

    def action_filter(self) -> None:
        tab = self._active_tab()
        if tab is not None:
            tab.show_filter()

    def action_refresh(self) -> None:
        tab = self._active_tab()
        if tab is not None:
            tab.refresh_data()
            self.notify("Refreshing…", title=tab.tab_name)

    def action_tab_action(self, key: str) -> None:
        tab = self._active_tab()
        if tab is not None:
            tab.dispatch_action(key)

    # --- profile browsing -----------------------------------------------------

    def browse_profile(self, profile_path: str, profile_name: str) -> None:
        """Switch all tabs to view a different profile's config.

        Sets ``COPILOT_HOME`` so all data providers and CLI commands target
        the profile directory. Call ``restore_default_profile()`` to revert.
        """
        if self._original_copilot_home is None:
            self._original_copilot_home = os.environ.get("COPILOT_HOME", "")
        os.environ["COPILOT_HOME"] = profile_path
        self._browsing_profile = profile_name
        with suppress(Exception):
            self.query_one("#status-bar", StatusBar).set_profile(f"browsing: {profile_name}")
        self._refresh_all_tabs()
        self.notify(
            f"Browsing profile: {profile_name}\nLaunch CLI: COPILOT_HOME={profile_path} copilot",
            title="Profiles",
        )
        # Copy launch command to clipboard
        launch_cmd = f'$env:COPILOT_HOME="{profile_path}"; copilot'
        self.copy_to_clipboard(launch_cmd)

    def restore_default_profile(self) -> None:
        """Restore the original COPILOT_HOME and refresh all tabs."""
        if self._original_copilot_home is None:
            return
        if self._original_copilot_home:
            os.environ["COPILOT_HOME"] = self._original_copilot_home
        else:
            os.environ.pop("COPILOT_HOME", None)
        self._browsing_profile = ""
        self._original_copilot_home = None

        # Restore status bar to show actual active profile (if any)
        from copilotsetup.data.profiles import detect_active_profile

        profile = detect_active_profile()
        with suppress(Exception):
            self.query_one("#status-bar", StatusBar).set_profile(profile)
        self._refresh_all_tabs()
        self.notify("Returned to default config", title="Profiles")

    def _refresh_all_tabs(self) -> None:
        """Refresh every tab's data after a profile switch."""
        for _label, pane_id, _cls in _TAB_DEFINITIONS:
            with suppress(Exception):
                tab = self.query_one(f"#content-{pane_id}", BaseTab)
                tab.refresh_data()

    # --- helpers --------------------------------------------------------------

    def _active_tab(self) -> BaseTab | None:
        try:
            tc = self.query_one(TabbedContent)
            pane = tc.active_pane
            if pane is None:
                return None
            tabs = pane.query(BaseTab)
            return tabs.first() if tabs else None
        except Exception:
            return None

    def _update_counts(self) -> None:
        counts: dict[str, int] = {}
        for _label, pane_id, _cls in _TAB_DEFINITIONS:
            try:
                tab = self.query_one(f"#content-{pane_id}", BaseTab)
                if tab._items:
                    counts[tab.tab_name.lower()] = len(tab._items)
            except Exception:
                continue
        with suppress(Exception):
            self.query_one("#status-bar", StatusBar).set_counts(counts)


def main() -> None:
    """Entry point for ``copilot-setup`` CLI."""
    if len(sys.argv) > 1 and sys.argv[1] == "doctor":
        from copilotsetup.doctor import run_cli

        raise SystemExit(run_cli())

    app = CopilotSetupApp()
    app.run()


if __name__ == "__main__":
    main()
