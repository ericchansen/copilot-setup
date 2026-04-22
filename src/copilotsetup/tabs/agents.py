"""Agents tab — shows discovered agent definition files."""

from __future__ import annotations

from typing import Any, ClassVar

from copilotsetup.data.agents import AgentInfo, AgentProvider
from copilotsetup.tabs.base import BaseTab


class AgentsTab(BaseTab):
    tab_name = "Agents"
    columns: ClassVar[list[tuple[str, int]]] = [
        ("Name", 25),
        ("Source", 15),
        ("Description", 55),
    ]
    available_actions: ClassVar[list[str]] = []

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._provider = AgentProvider()

    def load_items(self) -> list[AgentInfo]:
        return self._provider.load()

    def key_for(self, item: AgentInfo) -> str:
        return item.name

    def row_for(self, item: AgentInfo) -> tuple[str, str, str]:
        return (item.name, item.source, item.description)

    def detail_for(self, item: AgentInfo) -> str:
        parts = [
            f"[bold]Name:[/] {item.name}",
            f"[bold]Source:[/] {item.source}",
            f"[bold]Path:[/] {item.path}",
            f"[bold]Description:[/] {item.description}",
        ]
        return "\n".join(parts)
