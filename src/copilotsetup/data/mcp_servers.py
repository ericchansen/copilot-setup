"""MCP server data provider — reads from mcp-config.json and plugin bundles."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

from copilotsetup.config import config_json, installed_plugins_dir, mcp_config_json
from copilotsetup.utils.file_io import read_json


@dataclass(frozen=True)
class McpServerInfo:
    """A single MCP server entry from mcp-config.json or a plugin bundle."""

    name: str
    server_type: str = "local"
    command: str = ""
    args: tuple[str, ...] = ()
    url: str = ""
    source: str = "config"
    env_ok: bool = True
    missing_env: tuple[str, ...] = ()
    health: str = ""
    health_latency: str = ""

    @property
    def status(self) -> str:
        if not self.env_ok:
            return "broken"
        return "enabled"

    @property
    def reason(self) -> str:
        if not self.env_ok and self.missing_env:
            return f"env: {', '.join(self.missing_env)}"
        if not self.env_ok:
            return "env missing"
        return ""


def _check_env(env_overrides: dict | None) -> tuple[bool, tuple[str, ...]]:
    """Check if all required env vars exist.  Returns (all_ok, missing_names)."""
    if not env_overrides:
        return True, ()
    missing = []
    for val in env_overrides.values():
        if isinstance(val, str) and val.startswith("$"):
            var_name = val.lstrip("$").strip("{}")
            if var_name and var_name not in os.environ:
                missing.append(var_name)
    if missing:
        return False, tuple(missing)
    return True, ()


def _build_plugin_server_map() -> dict[str, str]:
    """Build a mapping of server_name → plugin_name from plugin .mcp.json files."""
    cfg = read_json(config_json())
    if not isinstance(cfg, dict):
        return {}
    plugins_dir = installed_plugins_dir()
    result: dict[str, str] = {}
    for entry in cfg.get("installedPlugins", []) or []:
        if not isinstance(entry, dict):
            continue
        plugin_name = entry.get("name", "")
        cache_path = entry.get("cache_path", "")
        if not plugin_name or not cache_path:
            continue
        mcp_file = plugins_dir / cache_path / ".mcp.json"
        if not mcp_file.is_file():
            continue
        try:
            data = json.loads(mcp_file.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                servers = data.get("mcpServers")
                if isinstance(servers, dict):
                    for srv_name in servers:
                        if srv_name not in result:
                            result[str(srv_name)] = str(plugin_name)
        except (json.JSONDecodeError, OSError):
            pass
    return result


def _load_plugin_only_servers(plugin_map: dict[str, str], already_seen: set[str]) -> list[McpServerInfo]:
    """Load servers declared in plugin .mcp.json but NOT in mcp-config.json."""
    cfg = read_json(config_json())
    if not isinstance(cfg, dict):
        return []
    plugins_dir = installed_plugins_dir()
    result: list[McpServerInfo] = []
    seen: set[str] = set()
    for entry in cfg.get("installedPlugins", []) or []:
        if not isinstance(entry, dict):
            continue
        plugin_name = entry.get("name", "")
        cache_path = entry.get("cache_path", "")
        if not plugin_name or not cache_path:
            continue
        mcp_file = plugins_dir / cache_path / ".mcp.json"
        if not mcp_file.is_file():
            continue
        try:
            data = json.loads(mcp_file.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                continue
            servers = data.get("mcpServers")
            if not isinstance(servers, dict):
                continue
            for srv_name, srv_entry in servers.items():
                if srv_name in already_seen or srv_name in seen:
                    continue
                if not isinstance(srv_entry, dict):
                    continue
                seen.add(srv_name)
                server_type = str(srv_entry.get("type", "local"))
                command = str(srv_entry.get("command", ""))
                args_raw = srv_entry.get("args") or []
                url = str(srv_entry.get("url", ""))
                env_overrides = srv_entry.get("env")
                env_ok, missing = _check_env(env_overrides if isinstance(env_overrides, dict) else None)
                result.append(
                    McpServerInfo(
                        name=str(srv_name),
                        server_type=server_type,
                        command=command,
                        args=tuple(str(a) for a in args_raw) if isinstance(args_raw, list) else (),
                        url=url,
                        source=str(plugin_name),
                        env_ok=env_ok,
                        missing_env=missing,
                    )
                )
        except (json.JSONDecodeError, OSError):
            pass
    return result


class McpServerProvider:
    """Read-only provider that loads MCP servers from config and plugin bundles."""

    def load(self) -> list[McpServerInfo]:
        # Build plugin → server mapping for source attribution
        plugin_map = _build_plugin_server_map()

        # 1. Servers from mcp-config.json
        data = read_json(mcp_config_json())
        config_servers: dict[str, dict] = {}
        if isinstance(data, dict):
            raw = data.get("mcpServers")
            if isinstance(raw, dict):
                config_servers = {k: v for k, v in raw.items() if isinstance(v, dict)}

        result: list[McpServerInfo] = []
        seen: set[str] = set()
        for name, entry in sorted(config_servers.items()):
            seen.add(name)
            server_type = str(entry.get("type", "local"))
            command = str(entry.get("command", ""))
            args_raw = entry.get("args") or []
            url = str(entry.get("url", ""))
            env_overrides = entry.get("env")
            env_ok, missing = _check_env(env_overrides if isinstance(env_overrides, dict) else None)
            source = plugin_map.get(name, "config")
            result.append(
                McpServerInfo(
                    name=str(name),
                    server_type=server_type,
                    command=command,
                    args=tuple(str(a) for a in args_raw) if isinstance(args_raw, list) else (),
                    url=url,
                    source=source,
                    env_ok=env_ok,
                    missing_env=missing,
                )
            )

        # 2. Plugin-bundled servers not in mcp-config.json
        plugin_only = _load_plugin_only_servers(plugin_map, seen)
        result.extend(plugin_only)

        return result
