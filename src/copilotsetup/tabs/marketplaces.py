"""Marketplaces tab — manage plugin marketplace registrations."""

from __future__ import annotations

import re
from typing import Any, ClassVar

from copilotsetup.data.marketplaces import MarketplaceInfo, MarketplaceProvider
from copilotsetup.tabs.base import BaseTab
from copilotsetup.utils.cli import run_copilot


class MarketplacesTab(BaseTab):
    tab_name = "Marketplaces"
    columns: ClassVar[list[tuple[str, int]]] = [
        ("Name", 25),
        ("Source", 35),
        ("Type", 12),
    ]
    available_actions: ClassVar[list[str]] = ["a", "x", "u", "m"]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._provider = MarketplaceProvider()

    def load_items(self) -> list[MarketplaceInfo]:
        return self._provider.load()

    def key_for(self, item: MarketplaceInfo) -> str:
        return item.name

    def row_for(self, item: MarketplaceInfo) -> tuple[str, str, str]:
        return (item.name, item.source, item.marketplace_type)

    def detail_for(self, item: MarketplaceInfo) -> str:
        return "\n".join(
            [
                f"[bold]Name:[/] {item.name}",
                f"[bold]Source:[/] {item.source}",
                f"[bold]Type:[/] {item.marketplace_type}",
            ]
        )

    def filter_text(self, item: MarketplaceInfo) -> str:
        return f"{item.name} {item.source}"

    def handle_add(self) -> None:
        from copilotsetup.screens.input_dialog import InputDialog

        def on_result(source: str | None) -> None:
            if source is None:
                return
            try:
                result = run_copilot("plugin", "marketplace", "add", source, timeout=60)
                if result.returncode == 0:
                    self.notify(f"Added marketplace from {source}", title="Marketplaces")
                    self.refresh_data()
                else:
                    msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
                    self.notify(
                        f"Failed: {msg[:200]}",
                        severity="error",
                        title="Marketplaces",
                    )
            except FileNotFoundError:
                self.notify("copilot CLI not found", severity="error", title="Marketplaces")
            except Exception as exc:
                self.notify(f"Error: {exc}", severity="error", title="Marketplaces")

        self.app.push_screen(
            InputDialog(
                prompt="Marketplace source (owner/repo, URL, or local path):",
                placeholder="e.g. github/copilot-plugins",
            ),
            on_result,
        )

    def handle_remove(self) -> None:
        item = self.get_selected_item()
        if item is None:
            self.notify("No marketplace selected", severity="warning", title="Marketplaces")
            return
        if item.marketplace_type == "builtin":
            self.notify(
                "Cannot remove built-in marketplaces",
                severity="warning",
                title="Marketplaces",
            )
            return
        try:
            result = run_copilot("plugin", "marketplace", "remove", item.name, timeout=30)
            if result.returncode == 0:
                self.notify(f"Removed {item.name}", title="Marketplaces")
                self.refresh_data()
            else:
                msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
                self.notify(
                    f"Failed: {msg[:200]}",
                    severity="error",
                    title="Marketplaces",
                )
        except FileNotFoundError:
            self.notify("copilot CLI not found", severity="error", title="Marketplaces")
        except Exception as exc:
            self.notify(f"Error: {exc}", severity="error", title="Marketplaces")

    def handle_upgrade(self) -> None:
        item = self.get_selected_item()
        name = item.name if item else None
        args = ["plugin", "marketplace", "update"]
        if name:
            args.append(name)
        try:
            result = run_copilot(*args, timeout=60)
            if result.returncode == 0:
                target = name or "all marketplaces"
                self.notify(f"Updated {target}", title="Marketplaces")
                self.refresh_data()
            else:
                msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
                self.notify(
                    f"Failed: {msg[:200]}",
                    severity="error",
                    title="Marketplaces",
                )
        except FileNotFoundError:
            self.notify("copilot CLI not found", severity="error", title="Marketplaces")
        except Exception as exc:
            self.notify(f"Error: {exc}", severity="error", title="Marketplaces")

    def handle_marketplace(self) -> None:
        item = self.get_selected_item()
        if item is None:
            self.notify("No marketplace selected", severity="warning", title="Browse")
            return
        try:
            result = run_copilot("plugin", "marketplace", "browse", item.name, timeout=30)
        except FileNotFoundError:
            self.notify("copilot CLI not found", severity="error", title="Browse")
            return
        except Exception as exc:
            self.notify(f"Error: {exc}", severity="error", title="Browse")
            return

        if result.returncode != 0:
            msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
            self.notify(f"Failed: {msg[:200]}", severity="error", title="Browse")
            return

        plugins: list[str] = []
        for line in result.stdout.splitlines():
            match = re.match(r"\s*[•◆]\s+(\S+)", line)
            if match:
                plugins.append(match.group(1))

        if not plugins:
            self.notify(f"No plugins in {item.name}", severity="warning", title="Browse")
            return

        from copilotsetup.screens.input_dialog import InputDialog

        available = ", ".join(plugins)

        def on_pick(choice: str | None) -> None:
            if choice is None:
                return
            choice = choice.strip()
            source = f"{choice}@{item.name}" if "@" not in choice else choice
            try:
                install_result = run_copilot("plugin", "install", source, timeout=120)
                if install_result.returncode == 0:
                    self.notify(f"Installed {source}", title="Browse")
                    self.refresh_data()
                else:
                    msg = install_result.stderr.strip() or install_result.stdout.strip() or "Unknown error"
                    self.notify(f"Failed: {msg[:200]}", severity="error", title="Browse")
            except FileNotFoundError:
                self.notify("copilot CLI not found", severity="error", title="Browse")
            except Exception as exc:
                self.notify(f"Error: {exc}", severity="error", title="Browse")

        self.app.push_screen(
            InputDialog(
                prompt=f"Available: {available}\nInstall which plugin?",
                placeholder=f"e.g. {plugins[0]}",
            ),
            on_pick,
        )
