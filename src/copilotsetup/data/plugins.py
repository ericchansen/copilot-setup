"""Plugins data provider — reads installed/enabled plugins from config.json."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from copilotsetup.config import config_json, installed_plugins_dir
from copilotsetup.utils.file_io import read_json


@dataclass(frozen=True)
class PluginInfo:
    """A single Copilot CLI plugin."""

    name: str
    source: str = ""
    version: str = ""
    installed: bool = False
    disabled: bool = False
    install_path: str = ""
    marketplace: str = ""
    bundled_skills: tuple[str, ...] = ()
    bundled_servers: tuple[str, ...] = ()
    bundled_agents: tuple[str, ...] = ()
    upgrade_available: bool = False
    upgrade_summary: str = ""

    @property
    def status(self) -> str:
        if not self.installed:
            return "missing"
        return "disabled" if self.disabled else "enabled"

    @property
    def reason(self) -> str:
        if not self.installed:
            return "not installed"
        return ""


class PluginProvider:
    """Read-only provider that loads plugins from ``config.json``."""

    def load(self) -> list[PluginInfo]:
        cfg = read_json(config_json())
        if not isinstance(cfg, dict):
            return []
        enabled_map = cfg.get("enabledPlugins", {}) or {}
        result: list[PluginInfo] = []
        for entry in cfg.get("installedPlugins", []) or []:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name")
            if not name:
                continue
            marketplace = entry.get("marketplace", "") or ""

            # Determine enabled state
            enabled = entry.get("enabled", True)
            for key in [name, f"{name}@{marketplace}", f"{name}@local"]:
                if key in enabled_map:
                    enabled = bool(enabled_map[key])
                    break

            # Find install path
            cache_path = entry.get("cache_path", "")
            install_path = ""
            if cache_path:
                candidate = installed_plugins_dir() / cache_path
                if candidate.is_dir():
                    install_path = str(candidate)

            # Scan for bundled content
            bundled_skills: list[str] = []
            bundled_servers: list[str] = []
            bundled_agents: list[str] = []
            if install_path:
                ip = Path(install_path)
                # Check for .mcp.json (bundled servers)
                mcp_json = ip / ".mcp.json"
                if mcp_json.is_file():
                    try:
                        mcp_data = json.loads(mcp_json.read_text(encoding="utf-8"))
                        if isinstance(mcp_data, dict):
                            servers = mcp_data.get("mcpServers")
                            if isinstance(servers, dict):
                                bundled_servers = list(servers.keys())
                    except (json.JSONDecodeError, OSError):
                        pass
                # Check for skills/ subdirectory
                skills_subdir = ip / "skills"
                if skills_subdir.is_dir():
                    bundled_skills = [d.name for d in skills_subdir.iterdir() if d.is_dir()]
                # Check for agents/ subdirectory
                agents_subdir = ip / "agents"
                if agents_subdir.is_dir():
                    bundled_agents = [
                        f.name.removesuffix(".agent.md")
                        for f in agents_subdir.iterdir()
                        if f.is_file() and f.name.endswith(".agent.md")
                    ]

            result.append(
                PluginInfo(
                    name=str(name),
                    source=marketplace or "local",
                    version=str(entry.get("version", "")),
                    installed=True,
                    disabled=not enabled,
                    install_path=install_path,
                    marketplace=marketplace,
                    bundled_skills=tuple(bundled_skills),
                    bundled_servers=tuple(bundled_servers),
                    bundled_agents=tuple(bundled_agents),
                )
            )
        return result


def set_plugin_enabled(name: str, enabled: bool) -> bool:
    """Enable or disable a plugin by editing config.json.

    Updates both ``installedPlugins[].enabled`` and the ``enabledPlugins`` map.
    Returns True on success.
    """
    cfg_path = config_json()
    if not cfg_path.is_file():
        return False

    data = read_json(cfg_path)
    if not isinstance(data, dict):
        return False

    found = False
    marketplace = ""
    for entry in data.get("installedPlugins", []) or []:
        if isinstance(entry, dict) and entry.get("name") == name:
            entry["enabled"] = enabled
            marketplace = entry.get("marketplace", "") or ""
            found = True
            break
    if not found:
        return False

    enabled_map = data.setdefault("enabledPlugins", {})
    canonical = f"{name}@{marketplace}" if marketplace else name
    candidates = [name, f"{name}@{marketplace}", f"{name}@local"] if marketplace else [name, f"{name}@local"]
    key = next((k for k in candidates if k in enabled_map), canonical)
    enabled_map[key] = enabled

    try:
        cfg_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        return False
    return True
