"""Extensions data provider — scans ~/.copilot/extensions/ for installed extensions."""

from __future__ import annotations

import json
from dataclasses import dataclass

from copilotsetup.config import extensions_dir


@dataclass(frozen=True)
class ExtensionInfo:
    """A single Copilot CLI extension."""

    name: str
    path: str = ""
    version: str = ""


class ExtensionProvider:
    """Read-only provider that scans the extensions directory."""

    def load(self) -> list[ExtensionInfo]:
        ext_dir = extensions_dir()
        if not ext_dir.is_dir():
            return []
        result: list[ExtensionInfo] = []
        for entry in sorted(ext_dir.iterdir()):
            if not entry.is_dir():
                continue
            version = ""
            pkg_json = entry / "package.json"
            if pkg_json.is_file():
                try:
                    data = json.loads(pkg_json.read_text(encoding="utf-8"))
                    version = str(data.get("version", "") or "")
                except (json.JSONDecodeError, OSError):
                    pass
            result.append(ExtensionInfo(name=entry.name, path=str(entry), version=version))
        return result
