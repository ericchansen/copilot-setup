"""Profiles data provider — scans ~/.copilot/profiles/ for configuration profiles."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from copilotsetup.config import copilot_home
from copilotsetup.utils.file_io import read_json


def _default_home() -> Path:
    """Return the real Copilot home, ignoring browse-mode overrides.

    When the TUI is browsing a profile, ``COPILOT_HOME`` points into a profile
    directory. Profile operations (list, create, delete, rename) must always
    use the true root so they can see and manage all profiles.

    If ``COPILOT_HOME`` points inside ``~/.copilot/profiles/``, we return
    ``~/.copilot/``.  Otherwise we return ``copilot_home()`` as-is.
    """
    home = copilot_home()
    default_profiles = Path.home() / ".copilot" / "profiles"
    try:
        home.resolve().relative_to(default_profiles.resolve())
        # COPILOT_HOME is inside profiles/ — return the real root
        return Path.home() / ".copilot"
    except ValueError:
        return home


def _read_profile_json(profile_path: Path, filename: str) -> dict | None:
    """Read a JSON/JSONC file from a profile directory, returning None on failure."""
    data = read_json(profile_path / filename)
    return data if isinstance(data, dict) else None


def _scan_profile(profile_path: Path) -> dict:
    """Scan a profile directory and return summary fields.

    Returns a dict with keys matching the extra ProfileInfo fields.
    """
    mcp_servers: list[str] = []
    plugins: list[str] = []
    lsp_servers: list[str] = []
    model = ""
    has_instructions = False
    session_count = 0

    # MCP servers from mcp-config.json
    mcp_cfg = _read_profile_json(profile_path, "mcp-config.json")
    if mcp_cfg:
        servers = mcp_cfg.get("mcpServers")
        if isinstance(servers, dict):
            mcp_servers = sorted(servers.keys())

    # Plugins from config.json
    cfg = _read_profile_json(profile_path, "config.json")
    if cfg:
        for entry in cfg.get("installedPlugins", []) or []:
            if isinstance(entry, dict):
                name = entry.get("name")
                if name:
                    plugins.append(str(name))

    # LSP servers from lsp-config.json
    lsp_cfg = _read_profile_json(profile_path, "lsp-config.json")
    if lsp_cfg:
        servers = lsp_cfg.get("lspServers")
        if isinstance(servers, dict):
            lsp_servers = sorted(servers.keys())

    # Model from settings.json
    settings = _read_profile_json(profile_path, "settings.json")
    if settings:
        model = str(settings.get("model", "") or "")

    # Custom instructions
    has_instructions = (profile_path / "copilot-instructions.md").is_file()

    # Session count
    session_dir = profile_path / "session-state"
    if session_dir.is_dir():
        session_count = sum(1 for d in session_dir.iterdir() if d.is_dir())

    return {
        "mcp_servers": tuple(mcp_servers),
        "plugins": tuple(plugins),
        "lsp_servers": tuple(lsp_servers),
        "model": model,
        "has_instructions": has_instructions,
        "session_count": session_count,
    }


def detect_active_profile() -> str:
    """Detect the active profile from ``COPILOT_HOME``.

    Returns the profile name if ``COPILOT_HOME`` points inside the default
    profiles directory (``~/.copilot/profiles/``), otherwise returns ``""``.
    """
    home = os.environ.get("COPILOT_HOME", "")
    if not home:
        return ""
    home_path = Path(home).resolve()
    # Always check against the default profiles dir, not the overridden one
    default_profiles = (Path.home() / ".copilot" / "profiles").resolve()
    try:
        rel = home_path.relative_to(default_profiles)
        parts = rel.parts
        if parts:
            return parts[0]
    except ValueError:
        pass
    return ""


def profile_server_matrix() -> dict[str, set[str]]:
    """Build a mapping of ``{server_name: {profile_names}}`` across all profiles."""
    prof_dir = _default_home() / "profiles"
    if not prof_dir.is_dir():
        return {}
    matrix: dict[str, set[str]] = {}
    for entry in prof_dir.iterdir():
        if not entry.is_dir():
            continue
        mcp_cfg = _read_profile_json(entry, "mcp-config.json")
        if not mcp_cfg:
            continue
        servers = mcp_cfg.get("mcpServers")
        if not isinstance(servers, dict):
            continue
        for server_name in servers:
            matrix.setdefault(server_name, set()).add(entry.name)
    return matrix


def create_profile(name: str, source_path: Path | None = None) -> Path:
    """Create a new profile by copying config files from *source_path*.

    Defaults to ``copilot_home()`` (root config) as the source.
    Returns the path to the new profile directory.
    Raises ``FileExistsError`` if the profile already exists.
    Raises ``ValueError`` if the name is empty or contains path separators.
    """
    if not name or "/" in name or "\\" in name:
        raise ValueError(f"Invalid profile name: {name!r}")

    target = _default_home() / "profiles" / name
    if target.exists():
        raise FileExistsError(f"Profile already exists: {target}")

    if source_path is None:
        source_path = _default_home()

    target.mkdir(parents=True)

    _CONFIG_FILES = [
        "config.json",
        "mcp-config.json",
        "lsp-config.json",
        "settings.json",
        "copilot-instructions.md",
    ]
    for filename in _CONFIG_FILES:
        src = source_path / filename
        if src.is_file():
            dst = target / filename
            dst.write_bytes(src.read_bytes())

    return target


def delete_profile(name: str) -> bool:
    """Delete a profile directory.

    Returns True on success, False if the profile doesn't exist.
    Raises ``ValueError`` if the name is empty or contains path separators.
    """
    if not name or "/" in name or "\\" in name:
        raise ValueError(f"Invalid profile name: {name!r}")

    target = _default_home() / "profiles" / name
    if not target.is_dir():
        return False

    import shutil

    shutil.rmtree(target)
    return True


def rename_profile(old_name: str, new_name: str) -> Path:
    """Rename a profile directory.

    Returns the new path.
    Raises ``ValueError`` if either name is invalid.
    Raises ``FileExistsError`` if *new_name* already exists.
    Raises ``FileNotFoundError`` if *old_name* doesn't exist.
    """
    for n in (old_name, new_name):
        if not n or "/" in n or "\\" in n:
            raise ValueError(f"Invalid profile name: {n!r}")

    src = _default_home() / "profiles" / old_name
    dst = _default_home() / "profiles" / new_name
    if not src.is_dir():
        raise FileNotFoundError(f"Profile not found: {old_name}")
    if dst.exists():
        raise FileExistsError(f"Profile already exists: {new_name}")
    src.rename(dst)
    return dst


@dataclass(frozen=True)
class ProfileInfo:
    """A single Copilot CLI configuration profile."""

    name: str
    path: str = ""
    active: bool = False
    is_default: bool = False
    mcp_servers: tuple[str, ...] = ()
    plugins: tuple[str, ...] = ()
    lsp_servers: tuple[str, ...] = ()
    model: str = ""
    has_instructions: bool = False
    session_count: int = 0


class ProfileProvider:
    """Read-only provider that scans the profiles directory."""

    def load(self) -> list[ProfileInfo]:
        home = _default_home()
        active_name = ""
        cfg = read_json(home / "config.json")
        if isinstance(cfg, dict):
            active_name = str(cfg.get("activeProfile", "") or "")

        # The root ~/.copilot/ is always shown as "(default)"
        is_default_active = not active_name
        default_scan = _scan_profile(home)
        result: list[ProfileInfo] = [
            ProfileInfo(
                name="(default)",
                path=str(home),
                active=is_default_active,
                is_default=True,
                **default_scan,
            )
        ]

        prof_dir = home / "profiles"
        if prof_dir.is_dir():
            for entry in sorted(prof_dir.iterdir()):
                if not entry.is_dir():
                    continue
                scan = _scan_profile(entry)
                result.append(
                    ProfileInfo(
                        name=entry.name,
                        path=str(entry),
                        active=entry.name == active_name,
                        **scan,
                    )
                )
        return result
