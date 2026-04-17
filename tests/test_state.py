"""Tests for the state layer — DashboardState computation."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from copilotsetup.state import (
    DashboardState,
    LspInfo,
    PluginInfo,
    ServerInfo,
    SkillInfo,
    SourceInfo,
    _check_env_vars,
    _discover_plugin_contents,
)


class TestSourceInfo:
    def test_basic_fields(self):
        info = SourceInfo(name="test", path=Path("/tmp/test"), exists=True, server_count=3)
        assert info.name == "test"
        assert info.server_count == 3
        assert info.exists is True

    def test_default_fields(self):
        info = SourceInfo(name="x", path=Path("/x"), exists=False)
        assert info.server_count == 0
        assert info.has_instructions is False
        assert info.has_portable is False
        assert info.has_lsp is False


class TestServerInfo:
    def test_http_status(self):
        srv = ServerInfo(name="s", source="src", server_type="http")
        assert srv.status == "configured"

    def test_local_ready(self):
        srv = ServerInfo(name="s", source="src", server_type="local", built=True)
        assert srv.status == "ready"

    def test_local_needs_build(self):
        srv = ServerInfo(name="s", source="src", server_type="local", built=False)
        assert srv.status == "needs build"

    def test_env_missing(self):
        srv = ServerInfo(name="s", source="src", server_type="local", built=True, env_ok=False)
        assert srv.status == "env missing"


class TestSkillInfo:
    def test_linked(self):
        skill = SkillInfo(name="sk", source="src", is_linked=True, link_ok=True)
        assert skill.status == "linked"

    def test_broken(self):
        skill = SkillInfo(name="sk", source="src", is_linked=True, link_ok=False)
        assert skill.status == "broken"

    def test_missing(self):
        skill = SkillInfo(name="sk", source="src")
        assert skill.status == "missing"


class TestPluginInfo:
    def test_enabled(self):
        plugin = PluginInfo(name="p", source="src", installed=True, version="1.0")
        assert plugin.status == "enabled"

    def test_disabled(self):
        plugin = PluginInfo(name="p", source="src", installed=True, disabled=True, version="1.0")
        assert plugin.status == "disabled"

    def test_missing(self):
        plugin = PluginInfo(name="p", source="src")
        assert plugin.status == "missing"

    def test_bundled_contents(self):
        plugin = PluginInfo(
            name="p",
            source="src",
            installed=True,
            version="1.0",
            bundled_skills=["skill-a", "skill-b"],
            bundled_servers=["server-x"],
            bundled_agents=["agent-1"],
            description="Test plugin",
            install_path="/some/path",
        )
        assert plugin.bundled_skills == ["skill-a", "skill-b"]
        assert plugin.bundled_servers == ["server-x"]
        assert plugin.bundled_agents == ["agent-1"]
        assert plugin.description == "Test plugin"


class TestLspInfo:
    def test_ready(self):
        lsp = LspInfo(name="ts", command="tsc", binary_ok=True)
        assert lsp.status == "ready"

    def test_missing(self):
        lsp = LspInfo(name="ts", command="tsc", binary_ok=False)
        assert lsp.status == "missing"


class TestDashboardState:
    def test_empty_state(self):
        state = DashboardState()
        assert state.drift_count == 0
        assert "No config sources" in state.summary_text

    def test_summary_text(self):
        state = DashboardState(
            sources=[SourceInfo(name="a", path=Path("/a"), exists=True)],
            servers=[ServerInfo(name="s", source="a", server_type="http")],
            skills=[],
            plugins=[],
            lsp_servers=[],
        )
        assert "1 sources" in state.summary_text
        assert "1 servers" in state.summary_text
        assert "✓ all synced" in state.summary_text

    def test_drift_count(self):
        state = DashboardState(
            sources=[SourceInfo(name="a", path=Path("/a"), exists=True)],
            servers=[ServerInfo(name="s", source="a", server_type="local", built=False)],
            skills=[SkillInfo(name="sk", source="a", is_linked=False)],
            plugins=[PluginInfo(name="p", source="a", installed=False)],
            lsp_servers=[LspInfo(name="l", command="cmd", binary_ok=False)],
        )
        assert state.drift_count == 4
        assert "⚠ 4 need attention" in state.summary_text


class TestHelpers:
    def test_check_env_vars_empty(self):
        assert _check_env_vars({}) is True
        assert _check_env_vars({"command": "node"}) is True

    def test_check_env_vars_with_values(self):
        with patch.dict("os.environ", {"MY_VAR": "set"}):
            assert _check_env_vars({"env": {"MY_VAR": "$MY_VAR"}}) is True

    def test_check_env_vars_missing(self):
        with patch.dict("os.environ", {}, clear=True):
            assert _check_env_vars({"env": {"MISSING": "$MISSING_VAR"}}) is False

    def test_discover_plugin_contents(self, tmp_path):
        """Scan a synthetic plugin directory for skills, servers, agents."""
        # Create plugin.json
        (tmp_path / "plugin.json").write_text('{"description": "Test plugin"}')

        # Create skills
        for name in ["skill-a", "skill-b"]:
            skill_dir = tmp_path / "skills" / name
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(f"# {name}")

        # Create .mcp.json with servers
        (tmp_path / ".mcp.json").write_text('{"mcpServers": {"srv-x": {}, "srv-y": {}}}')

        # Create agents
        (tmp_path / "agents" / "agent-1").mkdir(parents=True)

        desc, skills, servers, agents = _discover_plugin_contents(tmp_path)
        assert desc == "Test plugin"
        assert skills == ["skill-a", "skill-b"]
        assert servers == ["srv-x", "srv-y"]
        assert agents == ["agent-1"]

    def test_discover_plugin_contents_empty(self, tmp_path):
        """Empty directory returns empty lists."""
        desc, skills, servers, agents = _discover_plugin_contents(tmp_path)
        assert desc == ""
        assert skills == []
        assert servers == []
        assert agents == []

    def test_discover_plugin_legacy_skills(self, tmp_path):
        """Skills under .copilot/skills/ are detected."""
        skill_dir = tmp_path / ".copilot" / "skills" / "my-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("# my-skill")

        _, skills, _, _ = _discover_plugin_contents(tmp_path)
        assert skills == ["my-skill"]
