"""Readers for the vanilla Copilot CLI state in ``~/.copilot/``.

These functions let the dashboard populate itself from what Copilot CLI has
actually deployed on disk, independent of any ``config-sources.json`` overlay.
This makes the tool useful to users who don't use our source-based workflow.

All readers return empty/neutral values on missing or malformed inputs — they
never raise. Callers decide how to present absence.
"""

from __future__ import annotations

import json
from pathlib import Path

from copilotsetup.platform_ops import get_link_target, home_dir, is_link


def _copilot_home() -> Path:
    return home_dir() / ".copilot"


def read_mcp_config() -> dict[str, dict]:
    """Return the MCP servers Copilot CLI has registered in ``~/.copilot/mcp-config.json``.

    Entries are returned verbatim (keys preserved, including Copilot's own
    ``source``/``sourcePath`` stamps). Returns an empty dict if the file is
    missing, malformed, or empty.
    """
    path = _copilot_home() / "mcp-config.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    servers = data.get("mcpServers")
    if not isinstance(servers, dict):
        return {}
    return {str(k): v for k, v in servers.items() if isinstance(v, dict)}


def read_lsp_config() -> dict:
    """Return the LSP server map from ``~/.copilot/lsp-config.json``.

    Returns a dict with a single ``"lspServers"`` key (matching the on-disk
    shape) so callers can reuse existing merge logic. Empty dict on miss.
    """
    path = _copilot_home() / "lsp-config.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    servers = data.get("lspServers")
    if not isinstance(servers, dict):
        return {}
    return {"lspServers": {str(k): v for k, v in servers.items() if isinstance(v, dict)}}


def read_installed_plugins() -> dict[str, dict[str, object]]:
    """Read installed plugins from ``~/.copilot/config.json``.

    Returns ``{name: {"version": str, "disabled": bool, "source": str,
    "cache_path": str}}``. Empty dict on failure.

    Reads config.json directly rather than parsing ``copilot plugin list``
    output because the CLI format varies (marketplace plugins use
    ``name@source`` while local plugins are bare), strips the ``cache_path``
    field we need, and encodes the bullet glyph inconsistently on Windows.
    """
    path = _copilot_home() / "config.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}

    enabled_map = data.get("enabledPlugins", {}) or {}
    plugins: dict[str, dict[str, object]] = {}
    for entry in data.get("installedPlugins", []) or []:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        if not name:
            continue
        marketplace = entry.get("marketplace", "") or ""
        # Check both per-entry "enabled" and the enabledPlugins map, accepting
        # any of the variant keys Copilot CLI may have written.
        enabled = entry.get("enabled", True)
        candidates = [name]
        if marketplace:
            candidates.append(f"{name}@{marketplace}")
        candidates.append(f"{name}@local")
        for key in candidates:
            if key in enabled_map:
                enabled = bool(enabled_map[key])
                break
        plugins[name] = {
            "version": entry.get("version", ""),
            "disabled": not enabled,
            "source": marketplace or "local",
            "cache_path": entry.get("cache_path", ""),
        }
    return plugins


def scan_skill_links() -> dict[str, str]:
    """Return ``{skill_name: link_target_str}`` for every entry in ``~/.copilot/skills/``.

    A non-link entry (a real directory) maps to an empty string. Missing dir
    returns empty dict.
    """
    skills_dir = _copilot_home() / "skills"
    if not skills_dir.is_dir():
        return {}
    result: dict[str, str] = {}
    for entry in skills_dir.iterdir():
        target_str = ""
        if is_link(entry):
            target = get_link_target(entry)
            target_str = str(target) if target else ""
        result[entry.name] = target_str
    return result
