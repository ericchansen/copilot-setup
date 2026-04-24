"""Plugins tab — shows installed Copilot CLI plugins and bundled content."""

from __future__ import annotations

from typing import Any, ClassVar

from copilotsetup.data.plugins import PluginInfo, PluginProvider, set_plugin_enabled
from copilotsetup.tabs.base import BaseTab
from copilotsetup.utils.cli import run_copilot
from copilotsetup.widgets.status_render import Status, reason_cell, status_cell


class PluginsTab(BaseTab):
    tab_name = "Plugins"
    columns: ClassVar[list[tuple[str, int]]] = [
        ("Name", 20),
        ("Source", 12),
        ("Version", 10),
        ("Status", 10),
        ("Upgrade", 12),
        ("Reason", 20),
    ]
    available_actions: ClassVar[list[str]] = ["a", "x", "t", "u", "m"]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._provider = PluginProvider()

    def load_items(self) -> list[PluginInfo]:
        items = self._provider.load()
        self._check_upgrades_async(items)
        return items

    def _check_upgrades_async(self, items: list[PluginInfo]) -> None:
        """Kick off background upgrade detection for git-backed plugins."""
        import threading

        from copilotsetup.plugin_upgrades import check_all

        plugins = [(p.name, p.install_path, p.version) for p in items if p.installed]
        if not plugins:
            return

        def _run() -> None:
            try:
                results = check_all(plugins)
                upgrade_map = {r.name: r for r in results if r.upgrade_available}
                if upgrade_map:
                    self.call_from_thread(self._apply_upgrades, upgrade_map)
            except Exception:
                pass

        threading.Thread(target=_run, daemon=True).start()

    def _apply_upgrades(self, upgrade_map: dict) -> None:
        """Merge upgrade results into current items and refresh the table."""
        from dataclasses import replace

        new_items = []
        for item in self._items:
            info = upgrade_map.get(item.name)
            if info:
                item = replace(
                    item,
                    upgrade_available=True,
                    upgrade_summary=info.summary,
                )
            new_items.append(item)
        self._items = new_items
        self._apply_filter()

    def key_for(self, item: PluginInfo) -> str:
        return item.name

    def row_for(self, item: PluginInfo) -> tuple:
        status: Status = item.status  # type: ignore[assignment]
        upgrade = item.upgrade_summary or "—"
        return (
            item.name,
            item.source,
            item.version,
            status_cell(status),
            upgrade,
            reason_cell(item.reason),
        )

    def detail_for(self, item: PluginInfo) -> str:
        parts = [
            f"[bold]Name:[/] {item.name}",
            f"[bold]Source:[/] {item.source}",
            f"[bold]Version:[/] {item.version or '(unknown)'}",
            f"[bold]Status:[/] {item.status}",
        ]
        if item.upgrade_summary:
            parts.append(f"[bold]Upgrade:[/] [green]{item.upgrade_summary}[/green]")
        if item.reason:
            parts.append(f"[bold]Reason:[/] {item.reason}")
        if item.install_path:
            parts.append(f"[bold]Install path:[/] {item.install_path}")
        if item.bundled_skills:
            parts.append(f"[bold]Bundled skills:[/] {', '.join(item.bundled_skills)}")
        if item.bundled_servers:
            parts.append(f"[bold]Bundled servers:[/] {', '.join(item.bundled_servers)}")
        if item.bundled_agents:
            parts.append(f"[bold]Bundled agents:[/] {', '.join(item.bundled_agents)}")
        return "\n".join(parts)

    # --- action handlers ------------------------------------------------------

    def handle_add(self) -> None:
        self.notify(
            "Use `copilot plugin install <source>` to install",
            title="Install Plugin",
        )

    def handle_remove(self) -> None:
        item = self.get_selected_item()
        if item is None:
            self.notify("No plugin selected", severity="warning", title="Remove")
            return
        try:
            result = run_copilot("plugin", "uninstall", item.name)
            if result.returncode == 0:
                self.notify(f"Removed {item.name}", title="Remove Plugin")
                self.refresh_data()
            else:
                msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
                self.notify(f"Failed: {msg}", severity="error", title="Remove Plugin")
        except FileNotFoundError:
            self.notify("copilot CLI not found", severity="error", title="Remove Plugin")
        except Exception as exc:
            self.notify(f"Error: {exc}", severity="error", title="Remove Plugin")

    def handle_toggle(self) -> None:
        item = self.get_selected_item()
        if item is None:
            self.notify("No plugin selected", severity="warning", title="Toggle")
            return
        new_state = item.disabled  # flip: disabled→enable, enabled→disable
        action = "Enabled" if new_state else "Disabled"
        ok = set_plugin_enabled(item.name, new_state)
        if ok:
            self.notify(f"{action} [bold]{item.name}[/]", title="Toggle Plugin")
            self.refresh_data()
        else:
            self.notify(
                f"Failed to toggle {item.name}",
                severity="error",
                title="Toggle Plugin",
            )

    def handle_upgrade(self) -> None:
        item = self.get_selected_item()
        if item is None:
            self.notify("No plugin selected", severity="warning", title="Upgrade")
            return
        if not item.upgrade_available:
            self.notify(
                f"{item.name}: no upgrade available",
                severity="warning",
                title="Upgrade",
            )
            return
        self.notify(f"Upgrading {item.name}…", title="Upgrade Plugin")
        try:
            result = run_copilot("plugin", "update", item.name, timeout=180)
            if result.returncode == 0:
                self.notify(f"Upgraded {item.name}", title="Upgrade Plugin")
                self.refresh_data()
            else:
                msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
                self.notify(f"Failed: {msg}", severity="error", title="Upgrade Plugin")
        except FileNotFoundError:
            self.notify("copilot CLI not found", severity="error", title="Upgrade")
        except Exception as exc:
            self.notify(f"Error: {exc}", severity="error", title="Upgrade")

    def handle_marketplace(self) -> None:
        self.notify(
            "Use `copilot plugin marketplace browse` to discover plugins",
            title="Marketplace",
        )
