"""Dashboard state — desired configuration vs. actual filesystem state.

Computes what *should* exist (from merged config sources) alongside what
*actually* exists (on disk) and surfaces any drift between them.  All types
are plain dataclasses — no Textual reactive state lives here.
"""

from __future__ import annotations

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
    source: str  # which ConfigSource contributed it (or plugin name)
    server_type: str  # "http" or "local"
    configured: bool = True  # always True if it's in merged config
    built: bool = False  # local path on disk (for buildable servers)
    env_ok: bool = True  # environment variables present
    from_plugin: bool = False  # contributed by an installed plugin's .mcp.json
    plugin_installed: bool = False
    plugin_disabled: bool = False

    @property
    def status(self) -> str:
        if self.from_plugin:
            if not self.plugin_installed:
                return "missing"
            if self.plugin_disabled:
                return "disabled"
            if not self.env_ok:
                return "env missing"
            return "enabled"
        if not self.env_ok:
            return "env missing"
        if self.server_type == "http":
            return "configured"
        if self.built:
            return "ready"
        return "needs build"


@dataclass
class SkillInfo:
    """A skill from merged config with link/install status."""

    name: str
    source: str
    link_target: str = ""
    link_ok: bool = False
    is_linked: bool = False
    plugin_installed: bool = False
    plugin_disabled: bool = False

    @property
    def status(self) -> str:
        if self.is_linked:
            return "linked" if self.link_ok else "broken"
        if self.plugin_installed:
            return "disabled" if self.plugin_disabled else "enabled"
        return "missing"


@dataclass
class PluginInfo:
    """A plugin from merged config with install status."""

    name: str
    source: str  # which ConfigSource contributed it
    plugin_source: str = ""  # install source (URL, etc.)
    installed: bool = False
    disabled: bool = False
    version: str = ""
    description: str = ""
    install_path: str = ""
    bundled_skills: list[str] = field(default_factory=list)
    bundled_servers: list[str] = field(default_factory=list)
    bundled_agents: list[str] = field(default_factory=list)

    @property
    def status(self) -> str:
        if self.installed:
            return "disabled" if self.disabled else "enabled"
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
        count += sum(1 for s in self.servers if s.status not in ("ready", "configured", "enabled", "disabled"))
        count += sum(1 for s in self.skills if s.status not in ("linked", "enabled", "disabled"))
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


def _copilot_config_path() -> Path:
    """Return the path to ~/.copilot/config.json."""
    return home_dir() / ".copilot" / "config.json"


def _get_installed_plugins() -> dict[str, dict[str, object]]:
    """Read installed plugins from ``~/.copilot/config.json``.

    Returns {name: {"version": str, "disabled": bool, "source": str,
    "cache_path": str}}. Empty dict on failure.

    We read config.json directly rather than parsing ``copilot plugin list``
    output because the CLI format varies (marketplace plugins use
    ``name@source`` while local plugins are bare), strips the ``cache_path``
    field we need, and encodes the bullet glyph inconsistently on Windows.
    """
    import json

    cfg_path = _copilot_config_path()
    if not cfg_path.is_file():
        return {}

    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
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
        # Check both per-entry "enabled" field and the enabledPlugins map.
        # Accept any of the variant keys Copilot CLI may have written.
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


def set_plugin_enabled(name: str, enabled: bool) -> bool:
    """Enable or disable a plugin by editing ``~/.copilot/config.json``.

    Updates both ``installedPlugins[].enabled`` and the ``enabledPlugins`` map.
    Returns True on success.
    """
    import json

    cfg_path = _copilot_config_path()
    if not cfg_path.is_file():
        return False

    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False

    found = False
    marketplace = ""
    for entry in data.get("installedPlugins", []) or []:
        if isinstance(entry, dict) and entry.get("name") == name:
            entry["enabled"] = enabled
            # Preserve empty-string marketplace for direct-install plugins —
            # Copilot CLI's enabledPlugins key for those is the bare name, not
            # ``name@local``.
            marketplace = entry.get("marketplace", "") or ""
            found = True
            break
    if not found:
        return False

    enabled_map = data.setdefault("enabledPlugins", {})
    # Prefer an existing key form so we update in place; otherwise use the
    # canonical key for this plugin's marketplace (bare name when empty,
    # ``name@marketplace`` when a marketplace is set).
    canonical = f"{name}@{marketplace}" if marketplace else name
    candidates = [name, f"{name}@{marketplace}", f"{name}@local"] if marketplace else [name, f"{name}@local"]
    key = next((k for k in candidates if k in enabled_map), canonical)
    enabled_map[key] = enabled

    try:
        cfg_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        return False
    return True


def _discover_plugin_servers(plugin_dir: Path) -> dict[str, dict]:
    """Read a plugin's .mcp.json (or fallbacks) and return the server entries.

    Returns a mapping of server name → full entry dict, so callers can
    inspect ``url``, ``env``, etc. Returns empty dict on failure/missing.
    """
    import json

    for candidate in (
        plugin_dir / ".mcp.json",
        plugin_dir / "mcp.json",
        plugin_dir / ".copilot" / "mcp.json",
    ):
        if not candidate.is_file():
            continue
        try:
            data = json.loads(candidate.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        srv_dict = data.get("mcpServers", data)
        if isinstance(srv_dict, dict):
            return {str(k): v for k, v in srv_dict.items() if isinstance(v, dict)}
    return {}


def _discover_plugin_contents(plugin_dir: Path) -> tuple[str, list[str], list[str], list[str]]:
    """Scan a plugin directory for its bundled contents.

    Returns (description, skill_names, server_names, agent_names).
    """
    import json

    description = ""
    skills: list[str] = []
    servers: list[str] = []
    agents: list[str] = []

    # Read plugin.json for metadata
    plugin_json = plugin_dir / "plugin.json"
    if plugin_json.is_file():
        try:
            data = json.loads(plugin_json.read_text(encoding="utf-8"))
            description = data.get("description", "")
        except (json.JSONDecodeError, OSError):
            pass

    # Scan skills directory
    skills_dir = plugin_dir / "skills"
    if skills_dir.is_dir():
        skills = sorted(d.name for d in skills_dir.iterdir() if d.is_dir() and (d / "SKILL.md").exists())

    # Scan .copilot/skills (legacy layout)
    legacy_skills = plugin_dir / ".copilot" / "skills"
    if legacy_skills.is_dir() and not skills:
        skills = sorted(d.name for d in legacy_skills.iterdir() if d.is_dir() and (d / "SKILL.md").exists())

    # Read .mcp.json for bundled servers
    mcp_json = plugin_dir / ".mcp.json"
    if mcp_json.is_file():
        try:
            data = json.loads(mcp_json.read_text(encoding="utf-8"))
            srv_dict = data.get("mcpServers", data)
            if isinstance(srv_dict, dict):
                servers = sorted(srv_dict.keys())
        except (json.JSONDecodeError, OSError):
            pass

    # Also check mcp.json and .copilot/mcp.json
    for alt_path in [plugin_dir / "mcp.json", plugin_dir / ".copilot" / "mcp.json"]:
        if alt_path.is_file() and not servers:
            try:
                data = json.loads(alt_path.read_text(encoding="utf-8"))
                srv_dict = data.get("mcpServers", data)
                if isinstance(srv_dict, dict):
                    servers = sorted(srv_dict.keys())
            except (json.JSONDecodeError, OSError):
                pass

    # Scan agents directory
    agents_dir = plugin_dir / "agents"
    if agents_dir.is_dir():
        agents = sorted(d.name for d in agents_dir.iterdir() if d.is_dir())

    return description, skills, servers, agents


def _find_plugin_install_path(name: str, source: str, cache_path: str = "") -> Path | None:
    """Locate the install directory for a plugin.

    Prefers ``cache_path`` from ``installedPlugins[]`` (authoritative — it's
    exactly where Copilot CLI installed the plugin). Falls back to heuristics
    for plugins without a cache_path (e.g., loaded from a local dir).
    """
    # Prefer the authoritative cache_path from config.json
    if cache_path:
        cached = Path(cache_path).expanduser()
        if cached.is_dir():
            return cached

    plugins_root = home_dir() / ".copilot" / "installed-plugins"

    # Check installed-plugins/_direct/<org>--<name>/
    direct_dir = plugins_root / "_direct"
    if direct_dir.is_dir():
        for entry in direct_dir.iterdir():
            if entry.is_dir() and entry.name.endswith(f"--{name}") and any(entry.iterdir()):
                return entry

    # Check installed-plugins/<name>/<name>/ (cloned marketplace plugins)
    cloned = plugins_root / name / name
    if cloned.is_dir():
        return cloned

    # Check installed-plugins/<name>/ (flat layout)
    flat = plugins_root / name
    if flat.is_dir():
        return flat

    # Local plugin loaded via --plugin-dir or asPlugin source
    if source and "/" not in source and "\\" not in source:
        return None

    # Try resolving source as a local path
    source_path = Path(source).expanduser()
    if source_path.is_dir():
        return source_path

    return None


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
        meta = installed_plugins.get(name, {})
        installed = bool(meta)
        version = str(meta.get("version", "")) if meta else ""
        disabled = bool(meta.get("disabled", False))

        # Discover plugin contents
        description = ""
        bundled_skills: list[str] = []
        bundled_servers: list[str] = []
        bundled_agents: list[str] = []
        install_path_str = ""

        install_path = _find_plugin_install_path(name, plugin_source, str(meta.get("cache_path", "")))
        if install_path and install_path.is_dir():
            install_path_str = str(install_path)
            description, bundled_skills, bundled_servers, bundled_agents = _discover_plugin_contents(install_path)

        state.plugins.append(
            PluginInfo(
                name=name,
                source=source_name,
                plugin_source=plugin_source,
                installed=installed,
                disabled=disabled,
                version=version,
                description=description,
                install_path=install_path_str,
                bundled_skills=bundled_skills,
                bundled_servers=bundled_servers,
                bundled_agents=bundled_agents,
            )
        )

    # Source-registered plugins (asPlugin)
    for sp in merged.source_plugins:
        name = sp.get("name", "unknown")
        if not any(p.name == name for p in state.plugins):
            meta = installed_plugins.get(name, {})
            installed = bool(meta)
            version = str(meta.get("version", "")) if meta else ""
            disabled = bool(meta.get("disabled", False))

            # These are loaded from source paths — scan for contents
            description = ""
            bundled_skills: list[str] = []
            bundled_servers: list[str] = []
            bundled_agents: list[str] = []
            install_path_str = ""

            src_path = sp.get("path")
            if src_path:
                p = Path(str(src_path))
                if p.is_dir():
                    install_path_str = str(p)
                    description, bundled_skills, bundled_servers, bundled_agents = _discover_plugin_contents(p)

            state.plugins.append(
                PluginInfo(
                    name=name,
                    source="self",
                    plugin_source="local",
                    installed=installed,
                    disabled=disabled,
                    version=version,
                    description=description,
                    install_path=install_path_str,
                    bundled_skills=bundled_skills,
                    bundled_servers=bundled_servers,
                    bundled_agents=bundled_agents,
                )
            )

    # Add plugin-bundled skills that aren't already in the skills list
    existing_skill_names = {s.name for s in state.skills}
    for plugin in state.plugins:
        for skill_name in plugin.bundled_skills:
            if skill_name not in existing_skill_names:
                existing_skill_names.add(skill_name)
                is_linked = skill_name in linked_skills
                link_target = linked_skills.get(skill_name, "")
                link_ok = is_linked and (Path(link_target).is_dir() if link_target else False)
                state.skills.append(
                    SkillInfo(
                        name=skill_name,
                        source=plugin.name,
                        link_target=link_target,
                        link_ok=link_ok,
                        is_linked=is_linked,
                        plugin_installed=plugin.installed,
                        plugin_disabled=plugin.disabled,
                    )
                )

    # Add plugin-contributed MCP servers (from plugin's .mcp.json) that
    # aren't already in state.servers. Config-source entries win by source
    # order, matching the precedence for skills.
    existing_server_names = {s.name for s in state.servers}
    for plugin in state.plugins:
        if not plugin.install_path:
            continue
        plugin_servers = _discover_plugin_servers(Path(plugin.install_path))
        for srv_name, entry in plugin_servers.items():
            if srv_name in existing_server_names:
                continue
            existing_server_names.add(srv_name)
            server_type = "http" if "url" in entry else "local"
            state.servers.append(
                ServerInfo(
                    name=srv_name,
                    source=plugin.name,
                    server_type=server_type,
                    built=True,
                    env_ok=_check_env_vars(entry),
                    from_plugin=True,
                    plugin_installed=plugin.installed,
                    plugin_disabled=plugin.disabled,
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
