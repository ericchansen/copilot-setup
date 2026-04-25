"""Environment tab — shows Copilot-relevant environment variables."""

from __future__ import annotations

from typing import Any, ClassVar

from copilotsetup.data.environment import EnvironmentProvider, EnvVarInfo
from copilotsetup.tabs.base import BaseTab


class EnvironmentTab(BaseTab):
    tab_name = "Environment"
    columns: ClassVar[list[tuple[str, int]]] = [("Variable", 35), ("Value", 60)]
    available_actions: ClassVar[list[str]] = []

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._provider = EnvironmentProvider()

    def load_items(self) -> list[EnvVarInfo]:
        return self._provider.load()

    def key_for(self, item: EnvVarInfo) -> str:
        return item.name

    def row_for(self, item: EnvVarInfo) -> tuple[str, str]:
        return (item.name, item.value)

    def detail_for(self, item: EnvVarInfo) -> str:
        parts = [
            f"[bold]Variable:[/] {item.name}",
            f"[bold]Value:[/] {item.value}",
        ]
        if item.is_sensitive:
            parts.append("[yellow]⚠ Sensitive — value is masked[/]")
        return "\n".join(parts)
