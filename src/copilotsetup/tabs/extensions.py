"""Extensions tab — shows installed Copilot CLI extensions."""

from __future__ import annotations

from typing import Any, ClassVar

from copilotsetup.data.extensions import ExtensionInfo, ExtensionProvider
from copilotsetup.tabs.base import BaseTab


class ExtensionsTab(BaseTab):
    tab_name = "Extensions"
    columns: ClassVar[list[tuple[str, int]]] = [("Name", 30), ("Version", 15), ("Path", 50)]
    available_actions: ClassVar[list[str]] = []

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._provider = ExtensionProvider()

    def load_items(self) -> list[ExtensionInfo]:
        return self._provider.load()

    def key_for(self, item: ExtensionInfo) -> str:
        return item.name

    def row_for(self, item: ExtensionInfo) -> tuple[str, str, str]:
        return (item.name, item.version, item.path)

    def detail_for(self, item: ExtensionInfo) -> str:
        return "\n".join(
            [
                f"[bold]Name:[/] {item.name}",
                f"[bold]Version:[/] {item.version or '(unknown)'}",
                f"[bold]Path:[/] {item.path}",
            ]
        )
