"""Profiles data provider — scans ~/.copilot/profiles/ for configuration profiles."""

from __future__ import annotations

from dataclasses import dataclass

from copilotsetup.config import config_json, profiles_dir
from copilotsetup.utils.file_io import read_json


@dataclass(frozen=True)
class ProfileInfo:
    """A single Copilot CLI configuration profile."""

    name: str
    path: str = ""
    active: bool = False


class ProfileProvider:
    """Read-only provider that scans the profiles directory."""

    def load(self) -> list[ProfileInfo]:
        prof_dir = profiles_dir()
        if not prof_dir.is_dir():
            return []
        active_name = ""
        cfg = read_json(config_json())
        if isinstance(cfg, dict):
            active_name = str(cfg.get("activeProfile", "") or "")
        return [
            ProfileInfo(name=entry.name, path=str(entry), active=entry.name == active_name)
            for entry in sorted(prof_dir.iterdir())
            if entry.is_dir()
        ]
