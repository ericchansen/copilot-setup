"""Settings tab — shows user preferences from config.json."""

from __future__ import annotations

from typing import Any, ClassVar

from copilotsetup.data.settings import SettingInfo, SettingsProvider
from copilotsetup.tabs.base import BaseTab


class SettingsTab(BaseTab):
    tab_name = "Settings"
    columns: ClassVar[list[tuple[str, int]]] = [
        ("Setting", 35),
        ("Value", 25),
        ("Type", 10),
    ]
    available_actions: ClassVar[list[str]] = ["e"]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._provider = SettingsProvider()

    def load_items(self) -> list[SettingInfo]:
        return self._provider.load()

    def key_for(self, item: SettingInfo) -> str:
        return item.key

    def row_for(self, item: SettingInfo) -> tuple[str, str, str]:
        return (item.display_name, item.value, item.value_type)

    def detail_for(self, item: SettingInfo) -> str:
        return "\n".join(
            [
                f"[bold]Setting:[/] {item.key}",
                f"[bold]Value:[/] {item.value}",
                f"[bold]Type:[/] {item.value_type}",
                f"[bold]Status:[/] {item.status}",
            ]
        )

    def handle_edit(self) -> None:
        self.notify(
            "Setting edit not yet implemented",
            severity="warning",
            title="Settings",
        )
