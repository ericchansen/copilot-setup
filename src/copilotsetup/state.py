"""Dashboard state — desired configuration vs. actual filesystem state.

Computes what *should* exist (from merged config sources) alongside what
*actually* exists (on disk) and surfaces any drift between them.  All types
are plain dataclasses — no Textual reactive state lives here.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from copilotsetup.platform_ops import get_link_target, home_dir, is_link, validate_lsp_binary
from copilotsetup.skills import get_skill_folders
from copilotsetup.sources import ConfigSource, MergedConfig, discover_sources, load_source, merge_sources

# ---------------------------------------------------------------------------
# Per-item info dataclasses
# ---------------------------------------------------------------------------


@dataclass
class SourceInfo:
    """Summary of a single config source."""

    name: str
    path: Path
    exists: bool
    server_count: int = 0
    skill_count: int = 0
    plugin_count: int = 0
    has_instructions: bool = False
    has_portable: bool = False
    has_lsp: bool = False


@dataclass
class ServerInfo:
    """An MCP server from merged config with deployment status."""

    name: str
    source: str  # which ConfigSource contributed it
    server_type: str  # "http" or "local"
    configured: bool = True  # always True if it's in merged config
    built: bool = False  # local path on disk (for buildable servers)
    env_ok: bool = True  # environment variables present

    @property
    def status(self) -> str:
        if not self.env_ok:
            return "env missing"
        if self.server_type == "http":
            return "configured"
        if self.built:
            return "ready"
        return "needs build"


@dataclass
class SkillInfo:
    """A skill from merged config with link status."""

    name: str
    source: str
    link_target: str = ""
    link_ok: bool = False
    is_linked: bool = False

    @property
    def status(self) -> str:
        if not self.is_linked:
            return "missing"
        if self.link_ok:
            return "linked"
        return "broken"


@dataclass
class PluginInfo:
    """A plugin from merged config with install status."""

    name: str
    source: str  # which ConfigSource contributed it
    plugin_source: str = ""  # install source (URL, etc.)
    installed: bool = False
    version: str = ""

    @property
    def status(self) -> str:
        if self.installed:
            return "installed"
        return "missing"


@dataclass
class LspInfo:
    """An LSP server definition with binary validation status."""

    name: str
    command: str
    binary_ok: bool = False

    @property
    def status(self) -> str:
        if self.binary_ok:
            return "ready"
        return "missing"


# ---------------------------------------------------------------------------
# Aggregate dashboard state
# ---------------------------------------------------------------------------


@dataclass
class DashboardState:
    """Complete snapshot of desired + actual state for the TUI."""

    sources: list[SourceInfo] = field(default_factory=list)
    servers: list[ServerInfo] = field(default_factory=list)
    skills: list[SkillInfo] = field(default_factory=list)
    plugins: list[PluginInfo] = field(default_factory=list)
    lsp_servers: list[LspInfo] = field(default_factory=list)

    # Raw merged config (for action execution)
    merged: MergedConfig | None = None
    raw_sources: list[ConfigSource] = field(default_factory=list)

    @property
    def drift_count(self) -> int:
        """Number of items where actual ≠ desired."""
        count = 0
        count += sum(1 for s in self.servers if s.status != "ready" and s.status != "configured")
        count += sum(1 for s in self.skills if s.status != "linked")
        count += sum(1 for p in self.plugins if not p.installed)
        count += sum(1 for lsp in self.lsp_servers if not lsp.binary_ok)
        return count

    @property
    def summary_text(self) -> str:
        parts = []
        if not self.sources:
            return "No config sources found"
        parts.append(f"{len(self.sources)} sources")
        parts.append(f"{len(self.servers)} servers")
        parts.append(f"{len(self.skills)} skills")
        parts.append(f"{len(self.plugins)} plugins")
        parts.append(f"{len(self.lsp_servers)} LSP")
        drift = self.drift_count
        if drift:
            parts.append(f"⚠ {drift} need attention")
        else:
            parts.append("✓ all synced")
        return " │ ".join(parts)


# ---------------------------------------------------------------------------
# State loader
# ---------------------------------------------------------------------------


def _find_server_source(name: str, sources: list[ConfigSource]) -> str:
    """Find which source contributed a server by name."""
    for src in sources:
        if name in src.servers:
            return src.name
    return "unknown"


def _find_plugin_source(name: str, sources: list[ConfigSource]) -> str:
    """Find which source contributed a plugin by name."""
    for src in sources:
        if name in src.plugins:
            return src.name
    return "unknown"


def _check_env_vars(entry: dict) -> bool:
    """Check if all environment variables referenced in a server entry are set."""
    import os

    env = entry.get("env", {})
    for value in env.values():
        if isinstance(value, str) and value.startswith("$"):
            var_name = value.lstrip("$").strip("{}")
            if not os.environ.get(var_name):
                return False
    return True


def _get_installed_plugins() -> dict[str, str]:
    """Query ``copilot plugin list`` and parse installed plugins.

    Returns a dict of {name: version}.  Returns empty dict on failure.
    """
    if not shutil.which("copilot"):
        return {}

    import re
    import subprocess

    try:
        result = subprocess.run(
            ["copilot", "plugin", "list"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return {}
    except (subprocess.TimeoutExpired, OSError):
        return {}

    plugins: dict[str, str] = {}
    for line in result.stdout.splitlines():
        m = re.match(r"^\s*[•·]\s+(\S+?)(?:@\S+)?\s+\(v([\d.]+)\)", line)
        if m:
            plugins[m.group(1)] = m.group(2)
    return plugins


def load_dashboard_state() -> DashboardState:
    """Compute the full dashboard state from config sources + filesystem.

    This is the main entry point for populating the TUI.
    """
    state = DashboardState()
    copilot_home = home_dir() / ".copilot"
    copilot_skills = copilot_home / "skills"

    # Discover and load sources
    raw_sources = discover_sources()
    for src in raw_sources:
        load_source(src)
    state.raw_sources = raw_sources

    # Build source info
    for src in raw_sources:
        state.sources.append(
            SourceInfo(
                name=src.name,
                path=src.path,
                exists=src.exists,
                server_count=len(src.servers),
                skill_count=len(src.skill_dirs),
                plugin_count=len(src.plugins),
                has_instructions=src.instructions is not None,
                has_portable=src.portable_config is not None,
                has_lsp=src.lsp_servers is not None,
            )
        )

    # Merge
    merged = merge_sources(raw_sources)
    state.merged = merged

    # Servers
    for name, entry in merged.servers.items():
        if name in merged.disabled_by_default:
            continue
        source_name = _find_server_source(name, raw_sources)
        server_type = "http" if "url" in entry else "local"
        built = True  # assume ready unless we can prove otherwise
        if server_type == "local":
            # Check if there's a local path that should exist
            local_path = merged.local_paths.get(name)
            if local_path:
                built = Path(local_path).is_dir()

        state.servers.append(
            ServerInfo(
                name=name,
                source=source_name,
                server_type=server_type,
                built=built,
                env_ok=_check_env_vars(entry),
            )
        )

    # Skills — show what's deployed + what should be deployed
    # For plugin sources, skills come via the plugin mechanism (not skill_dirs).
    # For non-plugin sources, skills come from merged.skill_dirs.
    # In all cases, scan the deployed skills dir for actual state.

    linked_skills: dict[str, str] = {}
    if copilot_skills.is_dir():
        for entry in copilot_skills.iterdir():
            target_str = ""
            if is_link(entry):
                target = get_link_target(entry)
                target_str = str(target) if target else ""
            linked_skills[entry.name] = target_str

    # Desired skills from non-plugin sources
    all_skill_folders: list[dict] = []
    for skill_dir in merged.skill_dirs:
        all_skill_folders.extend(get_skill_folders(skill_dir))

    # Also scan source skill_dirs (even for plugin sources) to know provenance
    source_skill_map: dict[str, str] = {}  # skill_name → source_name
    for src in raw_sources:
        for sd in src.skill_dirs:
            if sd.is_dir():
                for folder in sd.iterdir():
                    if folder.is_dir() and (folder / "SKILL.md").exists() and folder.name not in source_skill_map:
                        source_skill_map[folder.name] = src.name

    # Build unified skill list: start from desired, then add deployed-only
    seen_skills: set[str] = set()
    for skill in all_skill_folders:
        name = skill["name"]
        if name in seen_skills:
            continue
        seen_skills.add(name)
        is_linked = name in linked_skills
        link_target = linked_skills.get(name, "")
        link_ok = is_linked and (Path(link_target).is_dir() if link_target else False)

        state.skills.append(
            SkillInfo(
                name=name,
                source=source_skill_map.get(name, "unknown"),
                link_target=link_target,
                link_ok=link_ok,
                is_linked=is_linked,
            )
        )

    # Add deployed skills not in desired (from plugins or other sources)
    for name, target_str in sorted(linked_skills.items()):
        if name in seen_skills:
            continue
        seen_skills.add(name)
        target_ok = Path(target_str).is_dir() if target_str else False
        state.skills.append(
            SkillInfo(
                name=name,
                source=source_skill_map.get(name, "plugin"),
                link_target=target_str,
                link_ok=target_ok,
                is_linked=True,
            )
        )

    # Plugins — desired from merged, actual from CLI
    installed_plugins = _get_installed_plugins()
    for name, info in merged.plugins.items():
        source_name = _find_plugin_source(name, raw_sources)
        plugin_source = info.get("source", "")
        installed = name in installed_plugins
        version = installed_plugins.get(name, "")

        state.plugins.append(
            PluginInfo(
                name=name,
                source=source_name,
                plugin_source=plugin_source,
                installed=installed,
                version=version,
            )
        )

    # Source-registered plugins (asPlugin)
    for sp in merged.source_plugins:
        name = sp.get("name", "unknown")
        if not any(p.name == name for p in state.plugins):
            installed = name in installed_plugins
            version = installed_plugins.get(name, "")
            state.plugins.append(
                PluginInfo(
                    name=name,
                    source="self",
                    plugin_source="local",
                    installed=installed,
                    version=version,
                )
            )

    # LSP servers
    if merged.lsp_servers and isinstance(merged.lsp_servers, dict):
        lsp_entries = merged.lsp_servers.get("lspServers", {})
        for name, cfg in lsp_entries.items():
            command = cfg.get("command", "")
            args = cfg.get("args", [])
            binary_ok = validate_lsp_binary(command, args)
            state.lsp_servers.append(
                LspInfo(
                    name=name,
                    command=command,
                    binary_ok=binary_ok,
                )
            )

    return state
