"""Inspect ``~/.copilot/mcp-oauth-config/`` to detect OAuth status per HTTP MCP server.

The Copilot CLI writes OAuth data for HTTP MCP servers in that directory:

    {hash}.json          — OAuth config (serverUrl, clientId, redirectUri…)
    {hash}.tokens.json   — access/refresh tokens (present after handshake completes)

This module maps ``serverUrl`` → ``OAuthStatus`` so the dashboard can surface
"Authenticated", "Needs OAuth", or "Not applicable" per HTTP server.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from copilotsetup.platform_ops import home_dir

logger = logging.getLogger(__name__)

OAuthStatus = Literal["authenticated", "needs_auth", "not_applicable", "unknown"]


@dataclass
class OAuthEntry:
    """One ``{hash}.json`` entry in the oauth-config dir."""

    server_url: str
    config_file: Path
    has_tokens: bool


def oauth_config_dir() -> Path:
    """Location of the Copilot CLI's OAuth config directory."""
    return home_dir() / ".copilot" / "mcp-oauth-config"


def scan_oauth_configs(config_dir: Path | None = None) -> list[OAuthEntry]:
    """Return every OAuth config found on disk.

    Non-JSON files and parse errors are logged and skipped (so a broken entry
    can't fail the whole dashboard).
    """
    config_dir = config_dir or oauth_config_dir()
    if not config_dir.is_dir():
        return []

    entries: list[OAuthEntry] = []
    for path in sorted(config_dir.iterdir()):
        if not path.is_file() or path.name.endswith(".tokens.json") or path.suffix != ".json":
            continue
        try:
            data = json.loads(path.read_text("utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.debug("Skipping unreadable oauth file %s: %s", path, exc)
            continue
        url = data.get("serverUrl", "")
        if not url:
            continue
        tokens_path = path.with_suffix(".tokens.json")
        has_tokens = tokens_path.is_file() and tokens_path.stat().st_size > 0
        entries.append(OAuthEntry(server_url=url, config_file=path, has_tokens=has_tokens))
    return entries


def build_status_map(entries: list[OAuthEntry]) -> dict[str, OAuthStatus]:
    """Collapse scanned entries into ``serverUrl → status``."""
    result: dict[str, OAuthStatus] = {}
    for entry in entries:
        result[entry.server_url] = "authenticated" if entry.has_tokens else "needs_auth"
    return result


def status_for(url: str, status_map: dict[str, OAuthStatus]) -> OAuthStatus:
    """Look up status for a given HTTP MCP URL, with trailing-slash tolerance.

    If no entry exists for the URL, we don't know whether the server uses OAuth
    (it may use static API keys in headers instead), so we return
    ``not_applicable`` rather than assuming it needs auth.
    """
    if url in status_map:
        return status_map[url]
    alt = url[:-1] if url.endswith("/") else url + "/"
    if alt in status_map:
        return status_map[alt]
    return "not_applicable"
