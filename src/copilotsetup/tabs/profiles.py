"""Profiles tab — shows Copilot CLI configuration profiles."""

from __future__ import annotations

from typing import Any, ClassVar

from copilotsetup.data.profiles import ProfileInfo, ProfileProvider
from copilotsetup.tabs.base import BaseTab


class ProfilesTab(BaseTab):
    tab_name = "Profiles"
    columns: ClassVar[list[tuple[str, int]]] = [("Name", 30), ("Active", 10), ("Path", 50)]
    available_actions: ClassVar[list[str]] = []

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._provider = ProfileProvider()

    def load_items(self) -> list[ProfileInfo]:
        return self._provider.load()

    def key_for(self, item: ProfileInfo) -> str:
        return item.name

    def row_for(self, item: ProfileInfo) -> tuple[str, str, str]:
        return (item.name, "✓" if item.active else "", item.path)

    def detail_for(self, item: ProfileInfo) -> str:
        status = "✓ Active" if item.active else "Inactive"
        return "\n".join(
            [
                f"[bold]Name:[/] {item.name}",
                f"[bold]Path:[/] {item.path}",
                f"[bold]Active:[/] {status}",
            ]
        )
