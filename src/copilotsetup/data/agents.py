"""Agents data provider — scans ~/.copilot/agents/ and plugin-bundled agents."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from copilotsetup.config import agents_dir, config_json, installed_plugins_dir
from copilotsetup.utils.file_io import read_json


@dataclass(frozen=True)
class AgentInfo:
    """A single agent definition file."""

    name: str
    path: str = ""
    description: str = ""
    source: str = ""


def _read_description(path: Path) -> str:
    """Read first non-empty line from an agent.md file."""
    try:
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.strip()
            if stripped:
                return stripped[:120]
    except OSError:
        pass
    return ""


class AgentProvider:
    """Read-only provider that scans agents directory and plugin bundles."""

    def load(self) -> list[AgentInfo]:
        result: list[AgentInfo] = []
        seen: set[str] = set()

        # 1. Agents from ~/.copilot/agents/
        ad = agents_dir()
        if ad.is_dir():
            for entry in sorted(ad.iterdir()):
                if not entry.is_file() or not entry.name.endswith(".agent.md"):
                    continue
                name = entry.name.removesuffix(".agent.md")
                seen.add(name)
                result.append(
                    AgentInfo(
                        name=name,
                        path=str(entry),
                        description=_read_description(entry),
                        source="user",
                    )
                )

        # 2. Plugin-bundled agents
        cfg = read_json(config_json())
        if isinstance(cfg, dict):
            plugins_dir = installed_plugins_dir()
            for entry in cfg.get("installedPlugins", []) or []:
                if not isinstance(entry, dict):
                    continue
                plugin_name = entry.get("name", "")
                cache_path = entry.get("cache_path", "")
                if not plugin_name or not cache_path:
                    continue
                agents_subdir = plugins_dir / cache_path / "agents"
                if not agents_subdir.is_dir():
                    continue
                for f in sorted(agents_subdir.iterdir()):
                    if f.is_file() and f.name.endswith(".agent.md"):
                        name = f.name.removesuffix(".agent.md")
                        if name not in seen:
                            seen.add(name)
                            result.append(
                                AgentInfo(
                                    name=name,
                                    path=str(f),
                                    description=_read_description(f),
                                    source=str(plugin_name),
                                )
                            )

        return result
