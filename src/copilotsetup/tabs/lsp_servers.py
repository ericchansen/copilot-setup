"""LSP Servers tab — shows configured language servers and binary status."""

from __future__ import annotations

from typing import Any, ClassVar

from copilotsetup.data.lsp_servers import LspInfo, LspServerProvider
from copilotsetup.tabs.base import BaseTab
from copilotsetup.widgets.status_render import Status, reason_cell, status_cell


class LspServersTab(BaseTab):
    tab_name = "LSP Servers"
    columns: ClassVar[list[tuple[str, int]]] = [
        ("Name", 25),
        ("Command", 35),
        ("Status", 10),
        ("Reason", 25),
    ]
    available_actions: ClassVar[list[str]] = []

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._provider = LspServerProvider()

    def load_items(self) -> list[LspInfo]:
        return self._provider.load()

    def key_for(self, item: LspInfo) -> str:
        return item.name

    def row_for(self, item: LspInfo) -> tuple:
        status: Status = item.status  # type: ignore[assignment]
        return (item.name, item.command, status_cell(status), reason_cell(item.reason))

    def detail_for(self, item: LspInfo) -> str:
        parts = [
            f"[bold]Name:[/] {item.name}",
            f"[bold]Command:[/] {item.command}",
        ]
        if item.args:
            parts.append(f"[bold]Args:[/] {' '.join(item.args)}")
        parts.append(f"[bold]Status:[/] {item.status}")
        if item.reason:
            parts.append(f"[bold]Reason:[/] {item.reason}")
        return "\n".join(parts)
