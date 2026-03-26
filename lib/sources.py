"""Config source discovery, loading, and merging.

A config source is a directory containing any combination of:
  - mcp-servers.json  → MCP server definitions
  - plugins.json      → Copilot CLI plugin definitions
  - lsp-servers.json  → LSP server definitions
  - config.portable.json → Portable Copilot settings
  - copilot-instructions.md → Global instructions
  - skills/           → Directory of skills (each with SKILL.md)

Sources are registered in ``~/.copilot/config-sources.json``::

    [
      {"name": "personal", "path": "C:/Users/you/repos/copilot-config"},
      {"name": "work",     "path": "C:/Users/you/repos/copilot-config-work"}
    ]

Merge strategy:
  - **Additive**: mcp-servers, plugins, skills — collected from all sources
  - **First-wins**: instructions, portable config, LSP servers — first source that provides it
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from lib.platform_ops import home_dir

logger = logging.getLogger(__name__)

SOURCES_FILE = "config-sources.json"

# Files the engine looks for in each config source
_MCP_SERVERS = "mcp-servers.json"
_PLUGINS = "plugins.json"
_LSP_SERVERS = "lsp-servers.json"
_PORTABLE_JSON = "config.portable.json"
_INSTRUCTIONS = "copilot-instructions.md"
_SKILLS_DIR = "skills"

# Legacy locations (for backward compatibility during migration)
_LEGACY_COPILOT_DIR = ".copilot"


@dataclass
class ConfigSource:
    """One registered config source (a directory on disk)."""

    name: str
    path: Path

    # Loaded data (populated by load_source)
    servers: list[dict] = field(default_factory=list)
    plugins: list[dict] = field(default_factory=list)
    lsp_servers: dict | None = None
    portable_config: Path | None = None
    instructions: Path | None = None
    skill_dirs: list[Path] = field(default_factory=list)

    @property
    def exists(self) -> bool:
        return self.path.is_dir()


@dataclass
class MergedConfig:
    """Result of merging all config sources."""

    servers: list[dict] = field(default_factory=list)
    plugins: list[dict] = field(default_factory=list)
    lsp_servers: dict | None = None
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
    """Look for a file at source root or in legacy .copilot/ subdir."""
    # Prefer root-level
    candidate = source_path / filename
    if candidate.is_file():
        return candidate
    # Fall back to .copilot/ subdir (legacy layout)
    legacy = source_path / _LEGACY_COPILOT_DIR / filename
    if legacy.is_file():
        return legacy
    return None


def _find_skills_dir(source_path: Path) -> Path | None:
    """Look for skills/ at root or in legacy .copilot/skills/."""
    candidate = source_path / _SKILLS_DIR
    if candidate.is_dir():
        return candidate
    legacy = source_path / _LEGACY_COPILOT_DIR / _SKILLS_DIR
    if legacy.is_dir():
        return legacy
    return None


def load_source(source: ConfigSource) -> ConfigSource:
    """Populate a ConfigSource by scanning its directory for known files."""
    if not source.exists:
        logger.warning("Config source '%s' path does not exist: %s", source.name, source.path)
        return source

    # MCP servers (additive)
    mcp_file = _find_file(source.path, _MCP_SERVERS)
    if mcp_file:
        try:
            data = json.loads(mcp_file.read_text("utf-8"))
            raw_servers = data.get("servers", []) if isinstance(data, dict) else data
            # Strip "category" field — the engine doesn't need it
            for s in raw_servers:
                s.pop("category", None)
            source.servers = raw_servers
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load %s: %s", mcp_file, exc)

    # Plugins (additive)
    plugins_file = _find_file(source.path, _PLUGINS)
    if plugins_file:
        try:
            data = json.loads(plugins_file.read_text("utf-8"))
            source.plugins = data.get("plugins", []) if isinstance(data, dict) else data
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load %s: %s", plugins_file, exc)

    # LSP servers (first-wins)
    lsp_file = _find_file(source.path, _LSP_SERVERS)
    if lsp_file:
        try:
            source.lsp_servers = json.loads(lsp_file.read_text("utf-8"))
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
      - **Additive**: servers, plugins, skill_dirs — all collected
      - **First-wins**: lsp_servers, portable_config, instructions — first source providing it
    """
    merged = MergedConfig(sources=sources)

    for source in sources:
        # Additive: servers
        merged.servers.extend(source.servers)

        # Additive: plugins
        merged.plugins.extend(source.plugins)

        # Additive: skill dirs
        merged.skill_dirs.extend(source.skill_dirs)

        # First-wins: LSP servers
        if merged.lsp_servers is None and source.lsp_servers is not None:
            merged.lsp_servers = source.lsp_servers

        # First-wins: portable config
        if merged.portable_config is None and source.portable_config is not None:
            merged.portable_config = source.portable_config

        # First-wins: instructions
        if merged.instructions is None and source.instructions is not None:
            merged.instructions = source.instructions

    # Deduplicate servers by name (first occurrence wins)
    seen_names: set[str] = set()
    deduped: list[dict] = []
    for s in merged.servers:
        name = s.get("name", "")
        if name not in seen_names:
            seen_names.add(name)
            deduped.append(s)
        else:
            logger.info("Duplicate server '%s' — keeping first occurrence", name)
    merged.servers = deduped

    # Deduplicate plugins by name
    seen_plugins: set[str] = set()
    deduped_plugins: list[dict] = []
    for p in merged.plugins:
        name = p.get("name", "")
        if name not in seen_plugins:
            seen_plugins.add(name)
            deduped_plugins.append(p)
    merged.plugins = deduped_plugins

    return merged
