"""Settings tab — shows user preferences from config.json."""

from __future__ import annotations

import logging
from typing import Any, ClassVar

from copilotsetup.config import config_json
from copilotsetup.data.settings import SettingInfo, SettingsProvider
from copilotsetup.tabs.base import BaseTab
from copilotsetup.utils.file_io import read_json, write_json

logger = logging.getLogger(__name__)

# Known enum values for settings that have fixed choices.
_ENUM_SETTINGS: dict[str, list[str]] = {
    "model": [
        "claude-sonnet-4.6",
        "claude-sonnet-4.5",
        "claude-haiku-4.5",
        "claude-opus-4.7",
        "claude-opus-4.6",
        "claude-opus-4.5",
        "claude-sonnet-4",
        "gpt-5.5",
        "gpt-5.4",
        "gpt-5.3-codex",
        "gpt-5.2-codex",
        "gpt-5.2",
        "gpt-5.4-mini",
        "gpt-5-mini",
        "gpt-4.1",
    ],
    "theme": ["auto", "dark", "light"],
    "banner": ["always", "never", "once"],
    "logLevel": ["none", "error", "warning", "info", "debug", "all", "default"],
    "keepAlive": ["off", "on", "busy"],
}


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

    def _write_setting(self, key: str, value: object) -> bool:
        """Write a single setting to config.json, preserving other keys."""
        path = config_json()
        cfg = read_json(path)
        if not isinstance(cfg, dict):
            cfg = {}

        # Handle dotted keys like "chat.agent" → cfg["chat"]["agent"]
        parts = key.split(".")
        target = cfg
        for part in parts[:-1]:
            if part not in target or not isinstance(target[part], dict):
                target[part] = {}
            target = target[part]
        target[parts[-1]] = value

        try:
            write_json(path, cfg)
            return True
        except Exception:
            logger.exception("Failed to write %s", path)
            return False

    def handle_edit(self) -> None:
        item = self.get_selected_item()
        if item is None:
            self.notify("No setting selected", severity="warning", title="Settings")
            return

        # Boolean toggle — flip directly
        if item.value_type == "bool":
            new_val = item.value.lower() not in ("true", "1", "yes")
            if self._write_setting(item.key, new_val):
                self.notify(f"Set [bold]{item.key}[/] = {new_val}", title="Settings")
                self.refresh_data()
            else:
                self.notify(f"Failed to write {item.key}", severity="error", title="Settings")
            return

        # Enum setting — show choices in prompt
        if item.key in _ENUM_SETTINGS:
            from copilotsetup.screens.input_dialog import InputDialog

            choices = _ENUM_SETTINGS[item.key]
            options = ", ".join(choices)

            def on_enum(val: str | None) -> None:
                if val is None:
                    return
                val = val.strip()
                if val not in choices:
                    self.notify(f"Invalid value: {val}", severity="warning", title="Settings")
                    return
                if self._write_setting(item.key, val):
                    self.notify(f"Set [bold]{item.key}[/] = {val}", title="Settings")
                    self.refresh_data()
                else:
                    self.notify(f"Failed to write {item.key}", severity="error", title="Settings")

            self.app.push_screen(
                InputDialog(
                    prompt=f"{item.key} ({options}):",
                    default=item.value,
                    placeholder=f"e.g. {choices[0]}",
                ),
                on_enum,
            )
            return

        # String/other — free text input
        from copilotsetup.screens.input_dialog import InputDialog

        def on_text(val: str | None) -> None:
            if val is None:
                return
            if self._write_setting(item.key, val):
                self.notify(f"Set [bold]{item.key}[/] = {val}", title="Settings")
                self.refresh_data()
            else:
                self.notify(f"Failed to write {item.key}", severity="error", title="Settings")

        self.app.push_screen(
            InputDialog(prompt=f"{item.key}:", default=item.value),
            on_text,
        )
