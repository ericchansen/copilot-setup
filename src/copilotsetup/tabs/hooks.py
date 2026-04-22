"""Hooks tab — shows lifecycle hook definitions."""

from __future__ import annotations

from typing import Any, ClassVar

from copilotsetup.data.hooks import HookInfo, HookProvider
from copilotsetup.tabs.base import BaseTab


class HooksTab(BaseTab):
    tab_name = "Hooks"
    columns: ClassVar[list[tuple[str, int]]] = [
        ("Event", 25),
        ("Command", 50),
        ("Type", 10),
    ]
    available_actions: ClassVar[list[str]] = []

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._provider = HookProvider()

    def load_items(self) -> list[HookInfo]:
        return self._provider.load()

    def key_for(self, item: HookInfo) -> str:
        return f"{item.event}:{item.command}"

    def row_for(self, item: HookInfo) -> tuple[str, str, str]:
        return (item.event, item.command, item.hook_type)

    def detail_for(self, item: HookInfo) -> str:
        return "\n".join(
            [
                f"[bold]Event:[/] {item.event}",
                f"[bold]Command:[/] {item.command}",
                f"[bold]Type:[/] {item.hook_type}",
            ]
        )
