"""Verify that plugin_server_names is derived from install outcomes, not intent.

Updated for the source-based architecture: plugins and servers come from
merged config sources, not a hardcoded PLUGINS list or mcp-servers.json in the engine repo.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import patch

from copilot_setup.models import SetupContext
from copilot_setup.steps.plugins import PluginsStep

# Sample data matching what copilot-config-work would provide
_MSX_SERVER = {
    "name": "msx-mcp",
    "type": "local",
    "command": "node",
    "entryPoint": "dist/index.js",
    "repo": "https://github.com/mcaps-microsoft/MSX-MCP.git",
    "cloneDir": "MSX-MCP",
    "defaultPaths": [],
    "build": ["npm install", "npm run build"],
    "tools": ["*"],
    "pluginFallback": "mcaps-microsoft/MSX-MCP",
}

_MSX_PLUGIN = {
    "name": "msx-mcp",
    "source": "mcaps-microsoft/MSX-MCP",
    "localServerName": "msx-mcp",
    "alias": "copilot-msx",
}


def _make_ctx(tmp_path: Path, servers: list[dict] | None = None, plugins: list[dict] | None = None) -> SetupContext:
    """Build a SetupContext with injected servers and plugins (source-based model)."""
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
    # Inject merged data (as setup.py does)
    ctx.enabled_servers = servers or [_MSX_SERVER.copy()]
    ctx.merged_plugins = plugins or [_MSX_PLUGIN.copy()]
    return ctx


def test_empty_when_copilot_cli_missing(tmp_path: Path):
    """copilot not on PATH, no local clone → empty set."""
    ctx = _make_ctx(tmp_path)
    with (
        patch("lib.skills.shutil.which", return_value=None),
        patch("copilot_setup.steps.plugins.link_local_plugins"),
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
        patch("lib.skills.shutil.which", return_value="/usr/bin/copilot"),
        patch("lib.skills._run_copilot", side_effect=_fake),
        patch("copilot_setup.steps.plugins.link_local_plugins"),
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
        patch("lib.skills.shutil.which", return_value="/usr/bin/copilot"),
        patch("lib.skills._run_copilot", side_effect=_fake),
        patch("copilot_setup.steps.plugins.link_local_plugins"),
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
        patch("lib.skills.shutil.which", return_value="/usr/bin/copilot"),
        patch("lib.skills._run_copilot", side_effect=_fake),
        patch("copilot_setup.steps.plugins.link_local_plugins"),
    ):
        PluginsStep().run(ctx)
    assert ctx.plugin_server_names == {"msx-mcp"}


def test_present_when_local_clone_exists(tmp_path: Path):
    """Local clone detected → in the set even if copilot CLI is missing."""
    clone = tmp_path / "MSX-MCP"
    clone.mkdir()
    (clone / ".git").mkdir()
    (clone / "dist").mkdir()
    (clone / "dist" / "index.js").write_text("// stub")

    server = _MSX_SERVER.copy()
    server["defaultPaths"] = [str(clone)]

    ctx = _make_ctx(tmp_path, servers=[server])

    with (
        patch("lib.skills.shutil.which", return_value=None),
        patch("copilot_setup.steps.plugins.link_local_plugins"),
    ):
        PluginsStep().run(ctx)
    assert ctx.plugin_server_names == {"msx-mcp"}
    assert "msx-mcp" in ctx.local_clone_map


def test_no_plugins_in_sources(tmp_path: Path):
    """No plugins in any config source → no work to do."""
    ctx = _make_ctx(tmp_path, servers=[], plugins=[])
    result = PluginsStep().run(ctx)
    # The step should complete without error
    assert result is not None


if __name__ == "__main__":
    import tempfile

    tests = [
        ("empty when copilot CLI missing", test_empty_when_copilot_cli_missing),
        ("empty when install fails", test_empty_when_install_fails),
        ("present when already installed", test_present_when_already_installed),
        ("present when fresh install succeeds", test_present_when_fresh_install_succeeds),
        ("present when local clone exists", test_present_when_local_clone_exists),
        ("no plugins in sources", test_no_plugins_in_sources),
    ]
    for label, fn in tests:
        with tempfile.TemporaryDirectory() as td:
            fn(Path(td))
            print(f"PASS: {label}")
    print(f"\nAll {len(tests)} scenarios passed!")
