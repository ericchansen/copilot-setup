"""Permissions data provider — reads trusted folders and URL allow/deny lists."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from copilotsetup.config import config_json
from copilotsetup.utils.file_io import read_json

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PermissionEntry:
    """A single permission entry (trusted folder or URL rule)."""

    category: str  # "trustedFolders", "allowedUrls", "deniedUrls"
    value: str


class PermissionProvider:
    """Read-only provider that loads permission entries from ``config.json``."""

    def load(self) -> list[PermissionEntry]:
        cfg = read_json(config_json())
        if not isinstance(cfg, dict):
            return []
        entries: list[PermissionEntry] = []
        for category in ("trustedFolders", "allowedUrls", "deniedUrls"):
            values = cfg.get(category)
            if not isinstance(values, list):
                continue
            entries.extend(
                PermissionEntry(category=category, value=val) for val in values if isinstance(val, str) and val
            )
        return entries
