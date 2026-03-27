"""Config source discovery, loading, and merging.

A config source is a directory with a standard ``.copilot/`` layout::

    repo/
      .copilot/
        mcp.json                  ← standard mcpServers format
        local.json                ← gitignored: local paths, plugins, aliases
        copilot-instructions.md   ← global instructions
        config.portable.json      ← portable Copilot settings
        lsp-servers.json          ← LSP server definitions
        skills/                   ← skill directories with SKILL.md

Sources are registered in ``~/.copilot/config-sources.json``::

    [
      {"name": "personal", "path": "C:/Users/you/repos/copilot-config"},
      {"name": "work",     "path": "C:/Users/you/repos/copilot-config-work"}
    ]

Merge strategy:
  - **Additive**: mcp-servers, skills, local_paths, plugins — collected from all sources
  - **First-wins**: instructions, portable config, LSP servers — first source that provides it

Build recipes are auto-detected from directory contents (see ``lib/build_detect.py``).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from copilotsetup.platform_ops import home_dir

logger = logging.getLogger(__name__)

SOURCES_FILE = "config-sources.json"

# Standard .copilot/ directory layout
_COPILOT_DIR = ".copilot"
_MCP_JSON = "mcp.json"
_LOCAL_JSON = "local.json"
_LSP_SERVERS = "lsp-servers.json"
_PORTABLE_JSON = "config.portable.json"
_INSTRUCTIONS = "copilot-instructions.md"
_SKILLS_DIR = "skills"


@dataclass
class ConfigSource:
    """One registered config source (a directory on disk)."""

    name: str
    path: Path

    # Loaded data (populated by load_source)
    servers: dict[str, dict] = field(default_factory=dict)  # standard mcpServers format
    local_paths: dict[str, str] = field(default_factory=dict)  # server → local dev path
    plugins: dict[str, dict] = field(default_factory=dict)  # server → {source, alias}
    lsp_servers: dict | None = None
    lsp_servers_path: Path | None = None
    portable_config: Path | None = None
    instructions: Path | None = None
    skill_dirs: list[Path] = field(default_factory=list)

    @property
    def exists(self) -> bool:
        return self.path.is_dir()

    @property
    def copilot_dir(self) -> Path:
        """The .copilot/ directory for this source."""
        return self.path / _COPILOT_DIR


@dataclass
class MergedConfig:
    """Result of merging all config sources."""

    servers: dict[str, dict] = field(default_factory=dict)  # name → standard entry
    local_paths: dict[str, str] = field(default_factory=dict)  # server → local dev path
    plugins: dict[str, dict] = field(default_factory=dict)  # server → {source, alias}
    lsp_servers: dict | None = None
    lsp_servers_path: Path | None = None
    portable_config: Path | None = None
    instructions: Path | None = None
    skill_dirs: list[Path] = field(default_factory=list)
    sources: list[ConfigSource] = field(default_factory=list)


def _sources_file() -> Path:
    """Path to the config sources registry."""
    return home_dir() / ".copilot" / SOURCES_FILE


def discover_sources() -> list[ConfigSource]:
    """Read ``~/.copilot/config-sources.json`` and return registered sources.

    Returns an empty list if the file doesn't exist.
    """
    sf = _sources_file()
    if not sf.exists():
        logger.info("No config-sources.json found at %s", sf)
        return []

    try:
        data = json.loads(sf.read_text("utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read %s: %s", sf, exc)
        return []

    sources: list[ConfigSource] = []
    for entry in data:
        name = entry.get("name", "unnamed")
        raw_path = entry.get("path", "")
        path = Path(raw_path).expanduser().resolve()
        sources.append(ConfigSource(name=name, path=path))

    return sources


def _find_file(source_path: Path, filename: str) -> Path | None:
    """Look for a file in the source's .copilot/ directory, or at root as fallback."""
    # Prefer .copilot/ (standard layout)
    candidate = source_path / _COPILOT_DIR / filename
    if candidate.is_file():
        return candidate
    # Fall back to root (legacy layout)
    root = source_path / filename
    if root.is_file():
        return root
    return None


def _find_skills_dir(source_path: Path) -> Path | None:
    """Look for skills/ in .copilot/ or at root."""
    candidate = source_path / _COPILOT_DIR / _SKILLS_DIR
    if candidate.is_dir():
        return candidate
    root = source_path / _SKILLS_DIR
    if root.is_dir():
        return root
    return None


def load_source(source: ConfigSource) -> ConfigSource:
    """Populate a ConfigSource by scanning its directory for known files."""
    if not source.exists:
        logger.warning("Config source '%s' path does not exist: %s", source.name, source.path)
        return source

    # MCP servers — standard .copilot/mcp.json format (additive)
    mcp_file = _find_file(source.path, _MCP_JSON)
    if mcp_file:
        try:
            data = json.loads(mcp_file.read_text("utf-8"))
            source.servers = data.get("mcpServers", {})
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load %s: %s", mcp_file, exc)

    # Local overrides — .copilot/local.json (gitignored, engine-only)
    local_file = _find_file(source.path, _LOCAL_JSON)
    if local_file:
        try:
            local_data = json.loads(local_file.read_text("utf-8"))
            source.local_paths = local_data.get("paths", {})
            source.plugins = local_data.get("plugins", {})
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load %s: %s", local_file, exc)

    # LSP servers (first-wins)
    lsp_file = _find_file(source.path, _LSP_SERVERS)
    if lsp_file:
        try:
            source.lsp_servers = json.loads(lsp_file.read_text("utf-8"))
            source.lsp_servers_path = lsp_file
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load %s: %s", lsp_file, exc)

    # Portable config (first-wins — store path, not content)
    portable_file = _find_file(source.path, _PORTABLE_JSON)
    if portable_file:
        source.portable_config = portable_file

    # Instructions (first-wins — store path for symlinking)
    instructions_file = _find_file(source.path, _INSTRUCTIONS)
    if instructions_file:
        source.instructions = instructions_file

    # Skills (additive — collect the directory)
    skills_dir = _find_skills_dir(source.path)
    if skills_dir:
        source.skill_dirs = [skills_dir]

    return source


def merge_sources(sources: list[ConfigSource]) -> MergedConfig:
    """Merge loaded config sources into a unified configuration.

    Merge strategies:
      - **Additive**: servers, skill_dirs — all collected
      - **First-wins**: lsp_servers, portable_config, instructions — first source providing it

    Server deduplication: first source providing a server name wins.
    """
    merged = MergedConfig(sources=sources)

    for source in sources:
        # Additive: servers (first occurrence of each name wins)
        for name, entry in source.servers.items():
            if name not in merged.servers:
                merged.servers[name] = entry
            else:
                logger.info("Duplicate server '%s' — keeping first occurrence", name)

        # Additive: local paths (first occurrence of each name wins)
        for name, path in source.local_paths.items():
            if name not in merged.local_paths:
                merged.local_paths[name] = path

        # Additive: plugins (first occurrence of each name wins)
        for name, plugin in source.plugins.items():
            if name not in merged.plugins:
                merged.plugins[name] = plugin

        # Additive: skill dirs
        merged.skill_dirs.extend(source.skill_dirs)

        # First-wins: LSP servers
        if merged.lsp_servers is None and source.lsp_servers is not None:
            merged.lsp_servers = source.lsp_servers
            merged.lsp_servers_path = source.lsp_servers_path

        # First-wins: portable config
        if merged.portable_config is None and source.portable_config is not None:
            merged.portable_config = source.portable_config

        # First-wins: instructions
        if merged.instructions is None and source.instructions is not None:
            merged.instructions = source.instructions

    return merged
