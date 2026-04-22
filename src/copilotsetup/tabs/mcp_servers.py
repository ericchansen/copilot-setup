"""MCP Servers tab — shows configured MCP servers with health and actions."""

from __future__ import annotations

from typing import Any, ClassVar

from copilotsetup.data.mcp_servers import McpServerInfo, McpServerProvider
from copilotsetup.tabs.base import BaseTab
from copilotsetup.utils.cli import run_copilot
from copilotsetup.widgets.status_render import reason_cell, status_cell


class McpServersTab(BaseTab):
    tab_name = "MCP Servers"
    columns: ClassVar[list[tuple[str, int]]] = [
        ("Name", 25),
        ("Type", 8),
        ("Source", 15),
        ("Status", 10),
        ("Health", 10),
        ("Reason", 25),
    ]
    available_actions: ClassVar[list[str]] = ["a", "x", "h"]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._provider = McpServerProvider()

    def load_items(self) -> list[McpServerInfo]:
        return self._provider.load()

    def key_for(self, item: McpServerInfo) -> str:
        return item.name

    def row_for(self, item: McpServerInfo) -> tuple[Any, ...]:
        return (
            item.name,
            item.server_type,
            item.source,
            status_cell(item.status),  # type: ignore[arg-type]
            item.health or "—",
            reason_cell(item.reason),
        )

    def detail_for(self, item: McpServerInfo) -> str:
        parts = [
            f"[bold]Name:[/] {item.name}",
            f"[bold]Type:[/] {item.server_type}",
            f"[bold]Source:[/] {item.source}",
        ]
        if item.server_type == "http":
            parts.append(f"[bold]URL:[/] {item.url}")
        else:
            parts.append(f"[bold]Command:[/] {item.command}")
            if item.args:
                parts.append(f"[bold]Args:[/] {' '.join(item.args)}")
        parts.append(f"[bold]Status:[/] {item.status}")
        if item.reason:
            parts.append(f"[bold]Reason:[/] {item.reason}")
        if item.missing_env:
            parts.append(f"[bold]Missing env:[/] {', '.join(item.missing_env)}")
        if item.health:
            parts.append(f"[bold]Health:[/] {item.health}")
        if item.health_latency:
            parts.append(f"[bold]Latency:[/] {item.health_latency}")
        return "\n".join(parts)

    def handle_add(self) -> None:
        self.notify(
            "Use [bold]copilot mcp add[/] to add servers",
            title="MCP Servers",
        )

    def handle_remove(self) -> None:
        item = self.get_selected_item()
        if item is None:
            self.notify("No server selected", severity="warning", title="MCP Servers")
            return
        try:
            result = run_copilot("mcp", "remove", item.name)
            if result.returncode == 0:
                self.notify(f"Removed [bold]{item.name}[/]", title="MCP Servers")
                self.refresh_data()
            else:
                msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
                self.notify(
                    f"Failed to remove {item.name}: {msg}",
                    severity="error",
                    title="MCP Servers",
                )
        except FileNotFoundError:
            self.notify(
                "copilot CLI not found on PATH",
                severity="error",
                title="MCP Servers",
            )
        except Exception as exc:
            self.notify(
                f"Error: {exc}",
                severity="error",
                title="MCP Servers",
            )

    def handle_health(self) -> None:
        self.notify(
            "Health probing not yet available — doctor not ported",
            severity="warning",
            title="MCP Servers",
        )
