"""Profiles tab — shows Copilot CLI configuration profiles."""

from __future__ import annotations

from typing import Any, ClassVar

from copilotsetup.data.profiles import (
    ProfileInfo,
    ProfileProvider,
    create_profile,
    delete_profile,
    rename_profile,
)
from copilotsetup.tabs.base import BaseTab


class ProfilesTab(BaseTab):
    tab_name = "Profiles"
    columns: ClassVar[list[tuple[str, int]]] = [
        ("Name", 20),
        ("Active", 8),
        ("MCP", 6),
        ("Plugins", 8),
        ("LSP", 6),
        ("Model", 25),
        ("Sessions", 8),
    ]
    available_actions: ClassVar[list[str]] = ["a", "x", "e", "t"]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._provider = ProfileProvider()

    def load_items(self) -> list[ProfileInfo]:
        return self._provider.load()

    def key_for(self, item: ProfileInfo) -> str:
        return item.name

    def row_for(self, item: ProfileInfo) -> tuple[str, ...]:
        return (
            item.name,
            "\u2713" if item.active else "",
            str(len(item.mcp_servers)),
            str(len(item.plugins)),
            str(len(item.lsp_servers)),
            item.model or "\u2014",
            str(item.session_count),
        )

    def detail_for(self, item: ProfileInfo) -> str:
        active_text = "\u2713 Active" if item.active else "Inactive"
        parts = [
            f"[bold]Name:[/] {item.name}",
            f"[bold]Path:[/] {item.path}",
            f"[bold]Active:[/] {active_text}",
            "",
        ]
        if item.model:
            parts.append(f"[bold]Model:[/] {item.model}")
        parts.append(f"[bold]Custom Instructions:[/] {'yes' if item.has_instructions else 'no'}")
        parts.append(f"[bold]Sessions:[/] {item.session_count}")
        parts.append("")

        if not item.is_default:
            parts.append("[bold]Launch with this profile:[/]")
            parts.append(f"  [dim]pwsh>[/]  $env:COPILOT_HOME='{item.path}'; copilot")
            parts.append(f"  [dim]sh  >[/]  COPILOT_HOME='{item.path}' copilot")
            parts.append("")

        if item.mcp_servers:
            parts.append(f"[bold]MCP Servers ({len(item.mcp_servers)}):[/]")
            parts.extend(f"  {s}" for s in item.mcp_servers)
        else:
            parts.append("[bold]MCP Servers:[/] none")
        parts.append("")

        if item.plugins:
            parts.append(f"[bold]Plugins ({len(item.plugins)}):[/]")
            parts.extend(f"  {p}" for p in item.plugins)
        else:
            parts.append("[bold]Plugins:[/] none")
        parts.append("")

        if item.lsp_servers:
            parts.append(f"[bold]LSP Servers ({len(item.lsp_servers)}):[/]")
            parts.extend(f"  {s}" for s in item.lsp_servers)
        else:
            parts.append("[bold]LSP Servers:[/] none")

        return "\n".join(parts)

    def filter_text(self, item: ProfileInfo) -> str:
        return f"{item.name} {item.model} {' '.join(item.mcp_servers)} {' '.join(item.plugins)} {' '.join(item.lsp_servers)}"

    def handle_add(self) -> None:
        from copilotsetup.screens.input_dialog import InputDialog

        def on_result(name: str | None) -> None:
            if name is None:
                return
            try:
                path = create_profile(name)
                self.notify(f"Created profile: {path.name}", title="Profiles")
                self.refresh_data()
            except FileExistsError:
                self.notify(
                    f"Profile '{name}' already exists",
                    severity="warning",
                    title="Profiles",
                )
            except ValueError as exc:
                self.notify(f"Invalid name: {exc}", severity="error", title="Profiles")
            except Exception as exc:
                self.notify(f"Error: {exc}", severity="error", title="Profiles")

        self.app.push_screen(
            InputDialog(prompt="Profile name:", placeholder="e.g. work, dev, all"),
            on_result,
        )

    def handle_remove(self) -> None:
        item = self.get_selected_item()
        if item is None:
            self.notify("No profile selected", severity="warning", title="Profiles")
            return
        if item.is_default:
            self.notify(
                "Cannot delete the default profile",
                severity="warning",
                title="Profiles",
            )
            return
        try:
            if delete_profile(item.name):
                self.notify(f"Deleted profile: {item.name}", title="Profiles")
                self.refresh_data()
            else:
                self.notify(
                    f"Profile not found: {item.name}",
                    severity="warning",
                    title="Profiles",
                )
        except Exception as exc:
            self.notify(f"Error: {exc}", severity="error", title="Profiles")

    def handle_edit(self) -> None:
        item = self.get_selected_item()
        if item is None:
            self.notify("No profile selected", severity="warning", title="Profiles")
            return
        if item.is_default:
            self.notify(
                "Cannot rename the default profile",
                severity="warning",
                title="Profiles",
            )
            return

        from copilotsetup.screens.input_dialog import InputDialog

        def on_result(new_name: str | None) -> None:
            if new_name is None or new_name == item.name:
                return
            try:
                rename_profile(item.name, new_name)
                self.notify(f"Renamed: {item.name} \u2192 {new_name}", title="Profiles")
                self.refresh_data()
            except FileExistsError:
                self.notify(
                    f"Profile '{new_name}' already exists",
                    severity="warning",
                    title="Profiles",
                )
            except ValueError as exc:
                self.notify(f"Invalid name: {exc}", severity="error", title="Profiles")
            except Exception as exc:
                self.notify(f"Error: {exc}", severity="error", title="Profiles")

        self.app.push_screen(
            InputDialog(prompt="Rename profile:", default=item.name),
            on_result,
        )

    def handle_toggle(self) -> None:
        from copilotsetup.app import CopilotSetupApp

        app = self.app
        if not isinstance(app, CopilotSetupApp):
            return

        # If already browsing, restore default
        if app._browsing_profile:
            app.restore_default_profile()
            return

        item = self.get_selected_item()
        if item is None:
            self.notify("No profile selected", severity="warning", title="Profiles")
            return
        if item.is_default:
            self.notify("Already viewing default config", title="Profiles")
            return

        app.browse_profile(item.path, item.name)
