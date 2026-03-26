"""Configuration management — patch, generate MCP config, generate LSP config."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from lib.platform_ops import is_link, validate_lsp_binary


def patch_config_json(
    config_path: Path,
    portable_path: Path,
    allowed_keys: list[str],
) -> bool:
    """Merge portable settings into config.json for *allowed_keys* only."""
    if not portable_path.exists():
        return False

    try:
        config = json.loads(config_path.read_text("utf-8")) if config_path.exists() else {}
    except json.JSONDecodeError:
        config = {}

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

    return {"type": "local", "command": command, "args": args, "tools": tools}


def generate_mcp_config(
    servers: dict[str, dict],
    mcp_paths: dict,
    external_dir: Path,
    output_path: Path,
) -> None:
    """Write ``~/.copilot/mcp-config.json`` from the enabled server dict."""
    # Remove legacy symlink/junction if present
    if is_link(output_path):
        output_path.unlink()

    mcp_servers: dict = {}
    for name, entry in servers.items():
        mcp_servers[name] = _build_mcp_entry(name, entry, mcp_paths, external_dir)

    output_path.write_text(
        json.dumps({"mcpServers": mcp_servers}, indent=2) + "\n",
        "utf-8",
    )


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
