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
        assert srv.status == "enabled"

    def test_local_ready(self):
        srv = ServerInfo(name="s", source="src", server_type="local", built=True)
        assert srv.status == "enabled"

    def test_local_needs_build(self):
        srv = ServerInfo(name="s", source="src", server_type="local", built=False)
        assert srv.status == "broken"
        assert srv.reason == "build pending"

    def test_env_missing(self):
        srv = ServerInfo(
            name="s",
            source="src",
            server_type="local",
            built=True,
            env_ok=False,
            missing_env_var="FOO",
        )
        assert srv.status == "broken"
        assert srv.reason == "env: FOO"


class TestSkillInfo:
    def test_linked(self):
        skill = SkillInfo(name="sk", source="src", is_linked=True, link_ok=True)
        assert skill.status == "enabled"

    def test_broken(self):
        skill = SkillInfo(name="sk", source="src", is_linked=True, link_ok=False)
        assert skill.status == "broken"
        assert skill.reason == "dangling link"

    def test_missing(self):
        skill = SkillInfo(name="sk", source="src")
        assert skill.status == "missing"

    def test_provenance_source(self):
        skill = SkillInfo(name="sk", source="agency", is_linked=True, link_ok=True)
        assert skill.delivery_kind == "source"
        assert skill.source_label == "agency (source)"
        assert skill.provided_by == "symlink from agency"

    def test_provenance_plugin(self):
        skill = SkillInfo(name="sk", source="edge-browser", plugin_installed=True)
        assert skill.delivery_kind == "plugin"
        assert skill.source_label == "edge-browser (plugin)"
        assert skill.provided_by == "plugin edge-browser (bundled)"

    def test_provenance_plugin_disabled(self):
        skill = SkillInfo(name="sk", source="edge-browser", plugin_installed=True, plugin_disabled=True)
        assert skill.provided_by == "plugin edge-browser (bundled) — disabled"

    def test_provenance_broken(self):
        skill = SkillInfo(name="sk", source="src", is_linked=True, link_ok=False)
        assert skill.provided_by == "symlink from src — broken"

    def test_provenance_missing(self):
        skill = SkillInfo(name="sk", source="src")
        assert skill.delivery_kind == ""
        assert skill.source_label == "src"
        assert skill.provided_by == "not installed"


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
        assert lsp.status == "enabled"

    def test_missing(self):
        lsp = LspInfo(name="ts", command="tsc", binary_ok=False)
        assert lsp.status == "missing"


class TestDashboardState:
    def test_empty_state(self):
        state = DashboardState()
        assert state.drift_count == 0
        # With no sources and no deployed items, summary still shows live counts.
        summary = state.summary_text
        assert "0 servers" in summary
        assert "0 skills" in summary
        # No "sources" prefix when none are registered.
        assert "sources" not in summary
        assert "✓ all synced" in summary

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
        assert _check_env_vars({}) == (True, "")
        assert _check_env_vars({"command": "node"}) == (True, "")

    def test_check_env_vars_with_values(self):
        with patch.dict("os.environ", {"MY_VAR": "set"}):
            assert _check_env_vars({"env": {"MY_VAR": "$MY_VAR"}}) == (True, "")

    def test_check_env_vars_missing(self):
        with patch.dict("os.environ", {}, clear=True):
            assert _check_env_vars({"env": {"MISSING": "$MISSING_VAR"}}) == (False, "MISSING_VAR")

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


class TestSetPluginEnabled:
    """Verify enabledPlugins key form for direct-install vs marketplace plugins."""

    def _write_config(self, tmp_path, installed, enabled_plugins):
        import json

        cfg = tmp_path / "config.json"
        cfg.write_text(
            json.dumps({"installedPlugins": installed, "enabledPlugins": enabled_plugins}),
            encoding="utf-8",
        )
        return cfg

    def _read_enabled(self, cfg):
        import json

        return json.loads(cfg.read_text(encoding="utf-8")).get("enabledPlugins", {})

    def test_direct_install_uses_bare_name(self, tmp_path):
        """Plugin with empty marketplace should get ``name`` as the key, not ``name@local``."""
        from copilotsetup import state

        cfg = self._write_config(
            tmp_path,
            installed=[{"name": "msx-mcp", "marketplace": "", "enabled": False}],
            enabled_plugins={},
        )
        with patch.object(state, "_copilot_config_path", return_value=cfg):
            assert state.set_plugin_enabled("msx-mcp", True)
        em = self._read_enabled(cfg)
        assert em == {"msx-mcp": True}

    def test_marketplace_uses_at_syntax(self, tmp_path):
        """Marketplace plugin should get ``name@marketplace`` as the key."""
        from copilotsetup import state

        cfg = self._write_config(
            tmp_path,
            installed=[{"name": "maenifold", "marketplace": "maenifold-marketplace", "enabled": False}],
            enabled_plugins={},
        )
        with patch.object(state, "_copilot_config_path", return_value=cfg):
            assert state.set_plugin_enabled("maenifold", True)
        em = self._read_enabled(cfg)
        assert em == {"maenifold@maenifold-marketplace": True}

    def test_updates_existing_key_in_place(self, tmp_path):
        """If a variant key already exists, update it in place (don't add a duplicate)."""
        from copilotsetup import state

        cfg = self._write_config(
            tmp_path,
            installed=[{"name": "msx-mcp", "marketplace": "", "enabled": True}],
            enabled_plugins={"msx-mcp@local": True},
        )
        with patch.object(state, "_copilot_config_path", return_value=cfg):
            assert state.set_plugin_enabled("msx-mcp", False)
        em = self._read_enabled(cfg)
        # Legacy key preserved and updated — no duplicate new entry
        assert em == {"msx-mcp@local": False}

    def test_returns_false_when_plugin_missing(self, tmp_path):
        from copilotsetup import state

        cfg = self._write_config(tmp_path, installed=[], enabled_plugins={})
        with patch.object(state, "_copilot_config_path", return_value=cfg):
            assert state.set_plugin_enabled("nonexistent", True) is False


class TestFindPluginInstallPath:
    """_find_plugin_install_path prefers cache_path over heuristic guesses."""

    def test_uses_cache_path_when_valid(self, tmp_path):
        from copilotsetup.state import _find_plugin_install_path

        real = tmp_path / "real-install"
        real.mkdir()
        (real / "plugin.json").write_text("{}")
        result = _find_plugin_install_path("whatever", "", str(real))
        assert result == real

    def test_falls_back_when_cache_path_missing(self, tmp_path):
        from copilotsetup.state import _find_plugin_install_path

        # Non-existent cache_path, bare source (marketplace-style) — should return None
        result = _find_plugin_install_path("nope", "some-marketplace", str(tmp_path / "missing"))
        assert result is None


class TestLoadDashboardStateVanilla:
    """Tier-1 loading: ``~/.copilot/`` is read even with zero config sources."""

    def _setup(self, tmp_path, monkeypatch):
        """Stub deployed._copilot_home + platform_ops.home_dir to use tmp_path."""
        import copilotsetup.deployed as deployed_mod
        import copilotsetup.state as state_mod

        fake_home = tmp_path / "home"
        fake_dotcopilot = fake_home / ".copilot"
        fake_dotcopilot.mkdir(parents=True)
        monkeypatch.setattr(deployed_mod, "_copilot_home", lambda: fake_dotcopilot)
        monkeypatch.setattr(state_mod, "home_dir", lambda: fake_home)
        # Prevent any real source discovery
        monkeypatch.setattr(state_mod, "discover_sources", list)
        return fake_dotcopilot

    def test_vanilla_servers_populate_with_no_sources(self, tmp_path, monkeypatch):
        import json as _json

        from copilotsetup.state import load_dashboard_state

        home = self._setup(tmp_path, monkeypatch)
        (home / "mcp-config.json").write_text(
            _json.dumps(
                {
                    "mcpServers": {
                        "github": {"url": "https://api.githubcopilot.com/mcp/", "source": "user"},
                        "local-srv": {"command": "python", "args": ["-m", "srv"], "source": "user"},
                    }
                }
            ),
            encoding="utf-8",
        )

        state = load_dashboard_state()
        names = sorted(s.name for s in state.servers)
        assert names == ["github", "local-srv"]
        # Each server carries the Copilot "user" stamp as its source.
        by_name = {s.name: s for s in state.servers}
        assert by_name["github"].source == "user"
        assert by_name["github"].server_type == "http"
        assert by_name["local-srv"].server_type == "local"
        # Deployed local servers are considered "built" (they're on disk).
        assert by_name["local-srv"].built is True

    def test_vanilla_lsp_populates_with_no_sources(self, tmp_path, monkeypatch):
        import json as _json

        from copilotsetup.state import load_dashboard_state

        home = self._setup(tmp_path, monkeypatch)
        (home / "lsp-config.json").write_text(
            _json.dumps({"lspServers": {"typescript": {"command": "tsserver", "args": [], "fileExtensions": [".ts"]}}}),
            encoding="utf-8",
        )

        state = load_dashboard_state()
        assert len(state.lsp_servers) == 1
        assert state.lsp_servers[0].name == "typescript"

    def test_vanilla_plugins_populate_with_no_sources(self, tmp_path, monkeypatch):
        import json as _json

        from copilotsetup.state import load_dashboard_state

        home = self._setup(tmp_path, monkeypatch)
        (home / "config.json").write_text(
            _json.dumps(
                {
                    "installedPlugins": [
                        {
                            "name": "peon-ping",
                            "marketplace": "peon-ping-marketplace",
                            "version": "1.0.0",
                            "enabled": True,
                        }
                    ],
                    "enabledPlugins": {"peon-ping@peon-ping-marketplace": True},
                }
            ),
            encoding="utf-8",
        )

        state = load_dashboard_state()
        names = [p.name for p in state.plugins]
        assert "peon-ping" in names
        p = next(p for p in state.plugins if p.name == "peon-ping")
        # Installed but not declared by any source → source="user".
        assert p.source == "user"
        assert p.installed is True
        assert p.disabled is False

    def test_empty_copilot_home_yields_empty_state(self, tmp_path, monkeypatch):
        """With no ~/.copilot/ files at all, dashboard loads without error."""
        from copilotsetup.state import load_dashboard_state

        self._setup(tmp_path, monkeypatch)
        state = load_dashboard_state()
        assert state.servers == []
        assert state.plugins == []
        assert state.lsp_servers == []
        assert state.sources == []
        assert "0 servers" in state.summary_text
