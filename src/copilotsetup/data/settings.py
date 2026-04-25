"""Settings data provider — reads user preferences from config.json."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from copilotsetup.config import config_json
from copilotsetup.utils.file_io import read_json

logger = logging.getLogger(__name__)

# Keys that belong to other tabs — skip them here.
SKIP_KEYS = frozenset(
    {
        "hooks",
        "installedPlugins",
        "enabledPlugins",
        "mcpServers",
        "lspServers",
        "permissions",
        "networkPermissions",
        "commandPermissions",
        "trustedFolders",
        "allowedUrls",
        "deniedUrls",
    }
)


@dataclass(frozen=True)
class SettingInfo:
    """A single user-facing setting from config.json."""

    key: str
    display_name: str
    value: str
    value_type: str = "string"

    @property
    def status(self) -> str:
        return "enabled" if self.value.lower() in ("true", "1", "yes") else "custom"


def _value_type_for(val: object) -> str:
    if isinstance(val, bool):
        return "bool"
    if isinstance(val, list):
        return "list"
    return "string"


def _format_value(val: object) -> str:
    """Format a config value for display."""
    if isinstance(val, bool):
        return str(val)
    if isinstance(val, (int, float)):
        return str(val)
    if isinstance(val, str):
        return val
    if isinstance(val, list):
        if not val:
            return "[]"
        # For simple lists, comma-separate; for complex, use compact JSON
        if all(isinstance(v, str) for v in val):
            return ", ".join(str(v) for v in val)
        return json.dumps(val, separators=(",", ":"), ensure_ascii=False)
    if isinstance(val, dict):
        return json.dumps(val, separators=(",", ":"), ensure_ascii=False)
    return str(val)


class SettingsProvider:
    """Read-only provider that loads simple settings from ``config.json``.

    Skips keys owned by other tabs and flattens one level of nested dicts
    so that ``{"chat": {"agent": true}}`` becomes key ``chat.agent``.
    Lists are shown as comma-separated values.
    """

    def load(self) -> list[SettingInfo]:
        cfg = read_json(config_json())
        if not isinstance(cfg, dict):
            return []
        result: list[SettingInfo] = []
        for key, val in sorted(cfg.items()):
            if key in SKIP_KEYS:
                continue
            if isinstance(val, dict):
                for sub_key, sub_val in sorted(val.items()):
                    flat_key = f"{key}.{sub_key}"
                    result.append(
                        SettingInfo(
                            key=flat_key,
                            display_name=flat_key,
                            value=_format_value(sub_val),
                            value_type=_value_type_for(sub_val),
                        )
                    )
            elif isinstance(val, list):
                result.append(
                    SettingInfo(
                        key=key,
                        display_name=key,
                        value=_format_value(val),
                        value_type="list",
                    )
                )
            elif isinstance(val, (str, bool, int, float)):
                result.append(
                    SettingInfo(
                        key=key,
                        display_name=key,
                        value=str(val),
                        value_type=_value_type_for(val),
                    )
                )
        return result
