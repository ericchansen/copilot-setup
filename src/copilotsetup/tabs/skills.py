"""Skills tab — shows installed skills and their link status."""

from __future__ import annotations

from typing import Any, ClassVar

from copilotsetup.data.skills import SkillInfo, SkillProvider
from copilotsetup.tabs.base import BaseTab
from copilotsetup.widgets.status_render import Status, reason_cell, status_cell


class SkillsTab(BaseTab):
    tab_name = "Skills"
    columns: ClassVar[list[tuple[str, int]]] = [
        ("Name", 30),
        ("Source", 20),
        ("Status", 10),
        ("Reason", 30),
    ]
    available_actions: ClassVar[list[str]] = []

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._provider = SkillProvider()

    def load_items(self) -> list[SkillInfo]:
        return self._provider.load()

    def key_for(self, item: SkillInfo) -> str:
        return item.name

    def row_for(self, item: SkillInfo) -> tuple[Any, ...]:
        status: Status = item.status  # type: ignore[assignment]
        return (item.name, item.source, status_cell(status), reason_cell(item.reason))

    def detail_for(self, item: SkillInfo) -> str:
        status: Status = item.status  # type: ignore[assignment]
        delivery = "linked" if item.is_linked else "directory"
        parts = [
            f"[bold]Name:[/] {item.name}",
            f"[bold]Source:[/] {item.source}",
            f"[bold]Status:[/] {status}",
            f"[bold]Delivery:[/] {delivery}",
        ]
        if item.is_linked:
            parts.append(f"[bold]Link target:[/] {item.link_target}")
        if item.reason:
            parts.append(f"[yellow]⚠ {item.reason}[/]")
        return "\n".join(parts)
