"""MCP Servers tab — shows configured MCP servers with health and actions."""

from __future__ import annotations

import os
import shlex
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
        self._profile_matrix = None  # type: ignore[assignment]
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

        # Show which profiles include this server
        if getattr(self, "_profile_matrix", None) is None:
            from copilotsetup.data.profiles import profile_server_matrix

            self._profile_matrix = profile_server_matrix()
        profile_names = self._profile_matrix.get(item.name)
        if profile_names:
            names = ", ".join(sorted(profile_names))
            parts.append(f"\n[bold]Profiles:[/] {names}")

        return "\n".join(parts)

    def handle_add(self) -> None:
        from copilotsetup.screens.input_dialog import InputDialog

        def on_name(name: str | None) -> None:
            if name is None:
                return

            def on_target(target: str | None) -> None:
                if target is None:
                    return
                try:
                    target = target.strip()
                    if target.startswith(("http://", "https://")):
                        result = run_copilot("mcp", "add", "--transport", "http", name, target, timeout=60)
                    else:
                        parts = shlex.split(target, posix=(os.name != "nt"))
                        if os.name == "nt":
                            parts = [p.strip('"').strip("'") for p in parts]
                        result = run_copilot("mcp", "add", name, "--", *parts, timeout=60)
                    if result.returncode == 0:
                        self.notify(f"Added [bold]{name}[/]", title="MCP Servers")
                        self.refresh_data()
                    else:
                        msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
                        self.notify(f"Failed: {msg[:200]}", severity="error", title="MCP Servers")
                except FileNotFoundError:
                    self.notify("copilot CLI not found", severity="error", title="MCP Servers")
                except Exception as exc:
                    self.notify(f"Error: {exc}", severity="error", title="MCP Servers")

            self.app.push_screen(
                InputDialog(
                    prompt="URL or command (e.g. https://mcp.example.com or npx -y @pkg/server):",
                    placeholder="https://... for HTTP, or command args for stdio",
                ),
                on_target,
            )

        self.app.push_screen(
            InputDialog(prompt="Server name:", placeholder="e.g. my-server"),
            on_name,
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
        item = self.get_selected_item()
        if item is None:
            self.notify("No server selected", severity="warning", title="Health")
            return
        if not item.raw_entry:
            self.notify("No config entry available for probing", severity="warning", title="Health")
            return

        import threading

        from copilotsetup.doctor import probe_server_entry

        self.notify(f"Probing {item.name}…", title="Health")

        def _probe() -> None:
            result = probe_server_entry(item.name, dict(item.raw_entry))
            latency = f" ({result.latency_ms}ms)" if result.latency_ms else ""
            detail = f": {result.detail}" if result.detail else ""
            if result.health == "ok":
                msg = f"[bold]{item.name}[/] — ✓ ok{latency}{detail}"
                self.app.call_from_thread(self.notify, msg, title="Health")
            else:
                msg = f"[bold]{item.name}[/] — {result.health}{latency}{detail}"
                self.app.call_from_thread(
                    self.notify,
                    msg,
                    severity="error",
                    title="Health",
                )

        threading.Thread(target=_probe, daemon=True).start()
