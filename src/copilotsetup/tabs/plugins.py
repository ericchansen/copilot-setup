"""Plugins tab — shows installed Copilot CLI plugins and bundled content."""

from __future__ import annotations

import logging
from typing import Any, ClassVar

from copilotsetup.data.plugins import PluginInfo, PluginProvider, set_plugin_enabled
from copilotsetup.tabs.base import BaseTab
from copilotsetup.utils.cli import run_copilot
from copilotsetup.widgets.status_render import Status, reason_cell, status_cell

logger = logging.getLogger(__name__)


class PluginsTab(BaseTab):
    tab_name = "Plugins"
    columns: ClassVar[list[tuple[str, int]]] = [
        ("Name", 20),
        ("Marketplace", 16),
        ("Source", 8),
        ("Repo", 28),
        ("Version", 10),
        ("Status", 10),
        ("Upgrade", 12),
        ("Reason", 20),
    ]
    available_actions: ClassVar[list[str]] = ["a", "x", "t", "u", "j"]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._provider = PluginProvider()

    def load_items(self) -> list[PluginInfo]:
        return self._provider.load()

    def _populate(self, items: list, gen: int) -> None:
        """Override to kick off upgrade checks from the main thread."""
        super()._populate(items, gen)
        if gen != self._active_gen:
            return
        force = getattr(self, "_force_refresh", False)
        self._force_refresh = False
        self._check_upgrades_async(items, gen, force)

    def _check_upgrades_async(self, items: list[PluginInfo], gen: int, force: bool) -> None:
        """Kick off background upgrade detection for git-backed plugins.

        Uses two-phase loading on initial launch:
        Phase 1 — show cached results immediately (provisional, no network).
        Phase 2 — force-refresh from network and update display.
        Manual refresh (``r`` key) skips Phase 1 and goes straight to network.
        """
        import threading

        from copilotsetup.upgrade_cache import UpgradeCache

        plugins = [(p.name, p.install_path, p.version) for p in items if p.installed]
        if not plugins:
            return

        cache = UpgradeCache.get_instance()

        def _run() -> None:
            try:
                # Phase 1: cache-only pass, no network (skip if manual refresh)
                if not force:
                    cached_map: dict = {}
                    for name, path, version in plugins:
                        cached_latest = cache.get(name)
                        if cached_latest is not None:
                            from copilotsetup.plugin_upgrades import check_plugin

                            info = check_plugin(path, name, version, _cached_latest=cached_latest)
                            cached_map[name] = info
                    if cached_map:
                        self.app.call_from_thread(self._apply_upgrades, cached_map, gen, True)

                # Phase 2: force-refresh from network
                fresh_results = [cache.get_or_check(name, path, version, force=True) for name, path, version in plugins]
                fresh_map = {r.name: r for r in fresh_results}
                self.app.call_from_thread(self._apply_upgrades, fresh_map, gen, False)
            except Exception:
                logger.debug("Upgrade check failed", exc_info=True)

        threading.Thread(target=_run, daemon=True).start()

    def refresh_data(self) -> None:
        """Override to force bypass cache on manual refresh (``r`` key)."""
        self._force_refresh = True
        super().refresh_data()

    def _apply_upgrades(self, result_map: dict, gen: int, provisional: bool = False) -> None:
        """Merge upgrade results into current items and refresh the table."""
        if gen != self._active_gen:
            return  # stale result from a superseded load
        from dataclasses import replace

        new_items = []
        for item in self._items:
            info = result_map.get(item.name)
            if info and info.upgrade_available:
                item = replace(
                    item,
                    upgrade_available=True,
                    upgrade_summary=info.summary,
                    upgrade_version=info.latest_version,
                    upgrade_provisional=provisional,
                    dev_summary="",
                    dev_branch="",
                    dev_commits_ahead=0,
                    latest_release=info.latest_version,
                )
            elif info and info.dev_summary:
                item = replace(
                    item,
                    upgrade_available=False,
                    upgrade_summary="",
                    upgrade_version="",
                    upgrade_provisional=provisional,
                    dev_summary=info.dev_summary,
                    dev_branch=info.dev_branch,
                    dev_commits_ahead=info.dev_commits_ahead,
                    latest_release=info.latest_version,
                )
            else:
                item = replace(
                    item,
                    upgrade_available=False,
                    upgrade_summary="—",
                    upgrade_version="",
                    upgrade_provisional=provisional,
                    dev_summary="",
                    dev_branch="",
                    dev_commits_ahead=0,
                    latest_release=(info.latest_version if info else ""),
                )
            new_items.append(item)
        self._items = new_items
        self._apply_filter()

    def key_for(self, item: PluginInfo) -> str:
        return item.name

    def row_for(self, item: PluginInfo) -> tuple:
        status: Status = item.status  # type: ignore[assignment]
        if item.upgrade_summary:
            upgrade = item.upgrade_summary
        elif item.dev_summary:
            upgrade = item.dev_summary
        else:
            upgrade = "…"
        if item.upgrade_provisional and (item.upgrade_summary or item.dev_summary):
            upgrade = f"{upgrade} ⏳"
        return (
            item.name,
            item.marketplace or "—",
            item.source_type or "—",
            item.source_repo or "—",
            item.version,
            status_cell(status),
            upgrade,
            reason_cell(item.reason),
        )

    def detail_for(self, item: PluginInfo) -> str:
        parts = [
            f"[bold]Name:[/] {item.name}",
            f"[bold]Marketplace:[/] {item.marketplace or '—'}",
            f"[bold]Source:[/] {item.source_type or '—'}",
            f"[bold]Repo:[/] {item.source_repo or '—'}",
            f"[bold]Version:[/] {item.version or '(unknown)'}",
            f"[bold]Status:[/] {item.status}",
        ]
        if item.upgrade_summary:
            suffix = " [dim](cached)[/]" if item.upgrade_provisional else ""
            parts.append(f"[bold]Upgrade:[/] [green]{item.upgrade_summary}[/green]{suffix}")
        elif item.dev_summary:
            suffix = " [dim](cached)[/]" if item.upgrade_provisional else ""
            parts.append(f"[bold]Local install:[/] [yellow]{item.dev_summary}[/yellow]{suffix}")
            if item.dev_commits_ahead:
                parts.append(f"  [dim]{item.dev_commits_ahead} commit(s) past last ancestor tag[/dim]")
            if item.latest_release:
                parts.append(f"  [dim]Latest release on origin:[/dim] {item.latest_release}")
            path = item.install_path or "<path>"
            tag = item.latest_release or "<tag>"
            reinstall = f"{item.name}@{item.marketplace}" if item.marketplace else "<name>@<marketplace>"
            parts.append(
                f"  [dim]To pin to a release: cd {path}; git checkout {tag}; copilot plugin install {reinstall}[/dim]"
            )
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
        from copilotsetup.screens.input_dialog import InputDialog

        def on_result(source: str | None) -> None:
            if source is None:
                return
            try:
                result = run_copilot("plugin", "install", source, timeout=120)
                if result.returncode == 0:
                    self.notify(f"Installed {source}", title="Install Plugin")
                    self.refresh_data()
                else:
                    msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
                    self.notify(f"Failed: {msg[:200]}", severity="error", title="Install Plugin")
            except FileNotFoundError:
                self.notify("copilot CLI not found", severity="error", title="Install Plugin")
            except Exception as exc:
                self.notify(f"Error: {exc}", severity="error", title="Install Plugin")

        self.app.push_screen(
            InputDialog(
                prompt="Plugin source (owner/repo, plugin@marketplace, or URL):",
                placeholder="e.g. owner/repo, spark@copilot-plugins",
            ),
            on_result,
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
        if item.dev_summary:
            branch = item.dev_branch or "current branch"
            target = item.latest_release or "<tag>"
            self.notify(
                f"{item.name}: local dev install on branch [bold]{branch}[/]. "
                f"To pin to a release, run in the source repo: "
                f"[bold]git checkout {target}; copilot plugin install "
                f"{item.name}@{item.marketplace if item.marketplace else '<marketplace>'}[/]",
                severity="warning",
                title="Upgrade",
                timeout=12,
            )
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
                from copilotsetup.upgrade_cache import UpgradeCache

                UpgradeCache.get_instance().invalidate(item.name)
                self.notify(f"Upgraded {item.name}", title="Upgrade Plugin")
                self.refresh_data()
            else:
                msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
                self.notify(f"Failed: {msg}", severity="error", title="Upgrade Plugin")
        except FileNotFoundError:
            self.notify("copilot CLI not found", severity="error", title="Upgrade")
        except Exception as exc:
            self.notify(f"Error: {exc}", severity="error", title="Upgrade")
