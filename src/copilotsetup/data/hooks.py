"""Hooks data provider — reads hook definitions from config.json."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from copilotsetup.config import config_json
from copilotsetup.utils.file_io import read_json

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HookInfo:
    """A single hook entry tied to a lifecycle event."""

    event: str
    command: str
    hook_type: str = "command"


class HookProvider:
    """Read-only provider that loads hooks from ``config.json``."""

    def load(self) -> list[HookInfo]:
        cfg = read_json(config_json())
        if not isinstance(cfg, dict):
            return []
        hooks_map = cfg.get("hooks")
        if not isinstance(hooks_map, dict):
            return []
        result: list[HookInfo] = []
        for event_name, hook_list in hooks_map.items():
            if not isinstance(hook_list, list):
                continue
            for entry in hook_list:
                if not isinstance(entry, dict):
                    continue
                command = entry.get("command", "")
                if not command:
                    continue
                result.append(HookInfo(event=str(event_name), command=str(command)))
        return result
