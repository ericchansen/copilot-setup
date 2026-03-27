"""Verify that plugin_server_names is derived from install outcomes, not intent.

Updated for local.json-based architecture: plugins and local paths come from
local.json in config sources, servers from standard .copilot/mcp.json.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import patch

from copilotsetup.models import SetupContext
from copilotsetup.steps.plugins import PluginsStep

# Standard mcp.json entry for the server
_MSX_SERVER_ENTRY = {"command": "node", "args": ["dist/index.js"]}

# Plugin info (as it would appear in local.json)
_MSX_PLUGIN_INFO = {"source": "mcaps-microsoft/MSX-MCP", "alias": "copilot-msx"}


@dataclass
class FakeMergedConfig:
    """Minimal mock of MergedConfig for tests."""

    plugins: dict[str, dict] = field(default_factory=dict)
    local_paths: dict[str, str] = field(default_factory=dict)


def _make_ctx(
    tmp_path: Path,
    servers: dict[str, dict] | None = None,
    plugins: dict[str, dict] | None = None,
    local_paths: dict[str, str] | None = None,
) -> SetupContext:
    """Build a SetupContext with injected servers and merged config."""
    root = Path(__file__).resolve().parent.parent
    args = argparse.Namespace(clean_orphans=False, non_interactive=True)
    ctx = SetupContext(
        repo_root=root,
        copilot_home=Path.home() / ".copilot",
        config_json=Path.home() / ".copilot" / "config.json",
        external_dir=root / "external",
        repo_copilot=root / ".copilot",
        repo_skills=root / ".copilot" / "skills",
        mcp_servers_json=Path("__merged__"),
        lsp_servers_json=Path("__merged__"),
        portable_json=Path("__none__"),
        args=args,
    )
    ctx.enabled_servers = servers if servers is not None else {"msx-mcp": _MSX_SERVER_ENTRY.copy()}
    ctx.merged_config = FakeMergedConfig(
        plugins=plugins if plugins is not None else {"msx-mcp": _MSX_PLUGIN_INFO.copy()},
        local_paths=local_paths or {},
    )
    return ctx


def test_empty_when_copilot_cli_missing(tmp_path: Path):
    """copilot not on PATH, no local clone → empty set."""
    ctx = _make_ctx(tmp_path)
    with (
        patch("copilotsetup.skills.shutil.which", return_value=None),
        patch("copilotsetup.steps.plugins.link_local_plugins"),
    ):
        PluginsStep().run(ctx)
    assert ctx.plugin_server_names == set()


def test_empty_when_install_fails(tmp_path: Path):
    """copilot available but install returns None → failed → empty set."""
    ctx = _make_ctx(tmp_path)

    def _fake(args, *, check=True):
        if args == ["plugin", "list"]:
            return ""
        return None  # install fails

    with (
        patch("copilotsetup.skills.shutil.which", return_value="/usr/bin/copilot"),
        patch("copilotsetup.skills._run_copilot", side_effect=_fake),
        patch("copilotsetup.steps.plugins.link_local_plugins"),
    ):
        PluginsStep().run(ctx)
    assert ctx.plugin_server_names == set()


def test_present_when_already_installed(tmp_path: Path):
    """Plugin shows up in 'copilot plugin list' → skipped → in the set."""
    ctx = _make_ctx(tmp_path)

    def _fake(args, *, check=True):
        if args == ["plugin", "list"]:
            return "msx-mcp    mcaps-microsoft/MSX-MCP    1.0.0"
        return "ok"

    with (
        patch("copilotsetup.skills.shutil.which", return_value="/usr/bin/copilot"),
        patch("copilotsetup.skills._run_copilot", side_effect=_fake),
        patch("copilotsetup.steps.plugins.link_local_plugins"),
    ):
        PluginsStep().run(ctx)
    assert ctx.plugin_server_names == {"msx-mcp"}


def test_present_when_fresh_install_succeeds(tmp_path: Path):
    """Plugin not present, install succeeds → in the set."""
    ctx = _make_ctx(tmp_path)

    def _fake(args, *, check=True):
        if args == ["plugin", "list"]:
            return ""
        return "installed"

    with (
        patch("copilotsetup.skills.shutil.which", return_value="/usr/bin/copilot"),
        patch("copilotsetup.skills._run_copilot", side_effect=_fake),
        patch("copilotsetup.steps.plugins.link_local_plugins"),
    ):
        PluginsStep().run(ctx)
    assert ctx.plugin_server_names == {"msx-mcp"}


def test_present_when_local_clone_exists(tmp_path: Path):
    """Local clone detected → in the set even if copilot CLI is missing."""
    clone = tmp_path / "MSX-MCP"
    clone.mkdir()
    (clone / ".git").mkdir()

    ctx = _make_ctx(tmp_path, local_paths={"msx-mcp": str(clone)})

    with (
        patch("copilotsetup.skills.shutil.which", return_value=None),
        patch("copilotsetup.steps.plugins.link_local_plugins"),
    ):
        PluginsStep().run(ctx)
    assert ctx.plugin_server_names == {"msx-mcp"}
    assert "msx-mcp" in ctx.local_clone_map


def test_no_plugins_defined(tmp_path: Path):
    """No plugins in local.json → no work to do."""
    ctx = _make_ctx(tmp_path, servers={}, plugins={})
    result = PluginsStep().run(ctx)
    assert result is not None
