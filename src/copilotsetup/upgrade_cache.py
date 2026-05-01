"""Disk-backed cache for plugin upgrade check results.

Stores {latest_version, checked_at} per plugin under
~/.copilot/upgrade-cache.json. Cache entries expire after 24 hours.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Any

from copilotsetup.config import upgrade_cache_json
from copilotsetup.plugin_upgrades import (
    STATUS_UP_TO_DATE,
    STATUS_UPGRADABLE,
    PluginUpgradeInfo,
    check_plugin,
)
from copilotsetup.utils.file_io import read_json, write_json

logger = logging.getLogger(__name__)

_SCHEMA_VERSION = 1
_TTL = timedelta(hours=24)


class UpgradeCache:
    """Read-through cache for plugin upgrade check results."""

    _instance: UpgradeCache | None = None

    @classmethod
    def get_instance(cls) -> UpgradeCache:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self, path=None):
        self._path = path if path is not None else upgrade_cache_json()
        self._lock = threading.Lock()
        self._data: dict[str, Any] | None = None

    def _ensure_loaded(self) -> None:
        if self._data is not None:
            return
        raw = read_json(self._path)
        if isinstance(raw, dict) and raw.get("_version") == _SCHEMA_VERSION and isinstance(raw.get("plugins"), dict):
            self._data = raw
        else:
            self._data = {"_version": _SCHEMA_VERSION, "plugins": {}}

    def _flush(self) -> None:
        assert self._data is not None
        try:
            write_json(self._path, self._data)
        except Exception:
            logger.debug("upgrade_cache: failed to write %s", self._path, exc_info=True)

    def get(self, name: str) -> str | None:
        with self._lock:
            self._ensure_loaded()
            assert self._data is not None
            entry = self._data["plugins"].get(name)
        if not isinstance(entry, dict):
            return None
        try:
            checked_at = datetime.fromisoformat(entry["checked_at"])
            if datetime.now(timezone.utc) - checked_at >= _TTL:
                return None
            latest = entry.get("latest_version")
            return str(latest) if latest else None
        except (KeyError, ValueError, TypeError):
            return None

    def set(self, name: str, latest_version: str) -> None:
        with self._lock:
            self._ensure_loaded()
            assert self._data is not None
            self._data["plugins"][name] = {
                "latest_version": latest_version,
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }
            self._flush()

    def invalidate(self, name: str) -> None:
        with self._lock:
            self._ensure_loaded()
            assert self._data is not None
            if name in self._data["plugins"]:
                del self._data["plugins"][name]
                self._flush()

    def get_or_check(
        self, name: str, install_path: str, config_version: str = "", *, force: bool = False
    ) -> PluginUpgradeInfo:
        cached_latest = None if force else self.get(name)
        info = check_plugin(install_path, name, config_version, _cached_latest=cached_latest)
        if cached_latest is None:
            # Only cache when network was actually consulted.
            cacheable = info.status == STATUS_UPGRADABLE or (info.status == STATUS_UP_TO_DATE and info.network_verified)
            if cacheable:
                version_to_cache = info.latest_version or info.current_version
                if version_to_cache:
                    self.set(name, version_to_cache)
        return info
