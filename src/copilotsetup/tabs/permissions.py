"""Permissions tab — shows trusted folders and URL allow/deny lists."""

from __future__ import annotations

from typing import Any, ClassVar

from copilotsetup.data.permissions import PermissionEntry, PermissionProvider
from copilotsetup.tabs.base import BaseTab

_CATEGORY_LABELS: dict[str, str] = {
    "trustedFolders": "Trusted Folders",
    "allowedUrls": "Allowed URLs",
    "deniedUrls": "Denied URLs",
}


class PermissionsTab(BaseTab):
    tab_name = "Permissions"
    columns: ClassVar[list[tuple[str, int]]] = [
        ("Category", 20),
        ("Value", 70),
    ]
    available_actions: ClassVar[list[str]] = []

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._provider = PermissionProvider()

    def load_items(self) -> list[PermissionEntry]:
        return self._provider.load()

    def key_for(self, item: PermissionEntry) -> str:
        return f"{item.category}:{item.value}"

    def row_for(self, item: PermissionEntry) -> tuple[str, str]:
        return (item.category, item.value)

    def detail_for(self, item: PermissionEntry) -> str:
        label = _CATEGORY_LABELS.get(item.category, item.category)
        return "\n".join(
            [
                f"[bold]Category:[/] {label}",
                f"[bold]Value:[/] {item.value}",
            ]
        )
