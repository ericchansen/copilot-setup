"""Configuration management — patch, generate MCP config, generate LSP config."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from copilotsetup.platform_ops import is_link, validate_lsp_binary


def json_load_safe(path: Path) -> dict:
    """Load JSON from *path*, returning {} on missing file or parse error."""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text("utf-8"))
    except json.JSONDecodeError:
        return {}


def patch_config_json(
    config_path: Path,
    portable_path: Path,
    allowed_keys: list[str],
) -> bool:
    """Merge portable settings into config.json for *allowed_keys* only."""
    if not portable_path.exists():
        return False

    config = json_load_safe(config_path)

    try:
        portable = json.loads(portable_path.read_text("utf-8"))
    except json.JSONDecodeError:
        return False

    for key in allowed_keys:
        if key in portable:
            config[key] = portable[key]

    config_path.write_text(json.dumps(config, indent=2) + "\n", "utf-8")
    return True


# ---------------------------------------------------------------------------
# MCP config generation
# ---------------------------------------------------------------------------


def _build_mcp_entry(name: str, entry: dict, mcp_paths: dict, external_dir: Path) -> dict:
    """Build a single mcpServers entry for the final config.

    Entries are already in standard format from .copilot/mcp.json.
    For servers with local paths (from build step), resolve relative args
    to absolute paths.
    """
    # HTTP servers — pass through as-is
    if "url" in entry:
        result: dict = {"type": "http", "url": entry["url"]}
        if entry.get("headers"):
            result["headers"] = entry["headers"]
        if entry.get("env"):
            result["env"] = entry["env"]
        result["tools"] = entry.get("tools", ["*"])
        return result

    # Command-based servers
    command = entry.get("command", "")
    args = list(entry.get("args", []))
    tools = entry.get("tools", ["*"])

    # If we have a local build path, resolve relative args to absolute paths
    stored = mcp_paths.get(name)
    if stored:
        resolved_args = []
        for arg in args:
            candidate = Path(stored) / arg
            if candidate.exists():
                resolved_args.append(str(candidate.resolve()))
            else:
                resolved_args.append(arg)
        args = resolved_args

    result = {"type": "local", "command": command, "args": args, "tools": tools}
    if entry.get("env"):
        result["env"] = entry["env"]
    return result


def generate_mcp_config(
    servers: dict[str, dict],
    mcp_paths: dict,
    external_dir: Path,
    output_path: Path,
) -> dict[str, list[str]]:
    """Write ``~/.copilot/mcp-config.json`` from the enabled server dict.

    User-added servers (names not in *servers*) are preserved from the
    existing config file.  Managed servers always take precedence.

    Returns a dict with ``"preserved"`` and ``"overridden"`` server name
    lists for downstream reporting.
    """
    info: dict[str, list[str]] = {"preserved": [], "overridden": []}

    # Read existing config before any destructive operations
    existing = json_load_safe(output_path)
    existing_servers: dict = {}
    if isinstance(existing.get("mcpServers"), dict):
        existing_servers = existing["mcpServers"]

    # Remove legacy symlink/junction if present
    if is_link(output_path):
        output_path.unlink()

    # Build managed servers
    managed: dict = {}
    managed_names: set[str] = set(servers)
    for name, entry in servers.items():
        managed[name] = _build_mcp_entry(name, entry, mcp_paths, external_dir)

    # Preserve user-added servers (names not managed by any source)
    user_servers: dict = {}
    for name, entry in existing_servers.items():
        if name in managed_names:
            # Managed server overrides — warn only if the existing entry
            # looks different (i.e., user may have customized it)
            if entry != managed[name]:
                info["overridden"].append(name)
        else:
            user_servers[name] = entry
            info["preserved"].append(name)

    # Merge: managed first, then user-added
    mcp_servers = {**managed, **user_servers}

    # Preserve other top-level keys from the existing config
    output: dict = {k: v for k, v in existing.items() if k != "mcpServers"}
    output["mcpServers"] = mcp_servers

    output_path.write_text(
        json.dumps(output, indent=2) + "\n",
        "utf-8",
    )
    return info


# ---------------------------------------------------------------------------
# LSP config generation
# ---------------------------------------------------------------------------


def generate_lsp_config(
    lsp_json_path: Path,
    output_path: Path,
    ui,
) -> tuple[int, list[str]]:
    """Validate LSP server binaries and write ``~/.copilot/lsp-config.json``."""
    if not lsp_json_path.exists():
        ui.item("lsp-servers.json", "warn", "not found — skipping")
        return 0, []

    data = json.loads(lsp_json_path.read_text("utf-8"))
    source_servers: dict = data.get("lspServers", {})

    included: dict = {}
    skipped: list[str] = []

    for name, cfg in source_servers.items():
        command = cfg["command"]
        args = cfg.get("args", [])

        if validate_lsp_binary(command, args):
            included[name] = cfg
            ui.item(name, "success", f"{command} validated")
        else:
            if shutil.which(command):
                ui.item(name, "warn", f"{command} found but not functional")
            else:
                ui.item(name, "info", f"{command} not installed")
            skipped.append(name)

    # Remove stale symlink at output path if present
    if is_link(output_path):
        output_path.unlink()

    output_path.write_text(
        json.dumps({"lspServers": included}, indent=2) + "\n",
        "utf-8",
    )
    return len(included), skipped
