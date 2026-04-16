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
    def test_installed(self):
        plugin = PluginInfo(name="p", source="src", installed=True, version="1.0")
        assert plugin.status == "installed"

    def test_missing(self):
        plugin = PluginInfo(name="p", source="src")
        assert plugin.status == "missing"


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
