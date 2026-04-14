"""Tests for lib/sources.py — config source discovery, loading, and merging."""

from __future__ import annotations

import json
from pathlib import Path

from copilotsetup.sources import ConfigSource, load_source, merge_sources


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), "utf-8")


class TestLoadSource:
    def test_loads_servers_from_mcp_json(self, tmp_path: Path):
        """Standard .copilot/mcp.json format."""
        src_dir = tmp_path / "personal"
        copilot = src_dir / ".copilot"
        copilot.mkdir(parents=True)
        _write_json(
            copilot / "mcp.json",
            {
                "mcpServers": {
                    "azure-mcp": {"command": "npx", "args": ["-y", "@azure/mcp@latest"]},
                    "context7": {"url": "https://mcp.context7.com/mcp"},
                }
            },
        )

        source = ConfigSource(name="personal", path=src_dir)
        load_source(source)

        assert len(source.servers) == 2
        assert "azure-mcp" in source.servers
        assert "context7" in source.servers

    def test_loads_instructions(self, tmp_path: Path):
        src_dir = tmp_path / "personal"
        copilot = src_dir / ".copilot"
        copilot.mkdir(parents=True)
        (copilot / "copilot-instructions.md").write_text("# Instructions", "utf-8")

        source = ConfigSource(name="personal", path=src_dir)
        load_source(source)

        assert source.instructions is not None
        assert source.instructions.name == "copilot-instructions.md"

    def test_loads_skills_dir(self, tmp_path: Path):
        src_dir = tmp_path / "personal"
        skills = src_dir / ".copilot" / "skills" / "my-skill"
        skills.mkdir(parents=True)
        (skills / "SKILL.md").write_text("---\nname: my-skill\n---", "utf-8")

        source = ConfigSource(name="personal", path=src_dir)
        load_source(source)

        assert len(source.skill_dirs) == 1
        assert source.skill_dirs[0].name == "skills"

    def test_root_fallback(self, tmp_path: Path):
        """Files at root (legacy layout) are found as fallback."""
        src_dir = tmp_path / "legacy"
        src_dir.mkdir()
        (src_dir / "copilot-instructions.md").write_text("# Legacy", "utf-8")

        skills = src_dir / "skills" / "some-skill"
        skills.mkdir(parents=True)
        (skills / "SKILL.md").write_text("---\nname: some-skill\n---", "utf-8")

        source = ConfigSource(name="legacy", path=src_dir)
        load_source(source)

        assert source.instructions is not None
        assert len(source.skill_dirs) == 1

    def test_copilot_dir_preferred_over_root(self, tmp_path: Path):
        """.copilot/ is preferred when both exist."""
        src_dir = tmp_path / "both"
        src_dir.mkdir()
        (src_dir / "copilot-instructions.md").write_text("# Root", "utf-8")
        copilot = src_dir / ".copilot"
        copilot.mkdir()
        (copilot / "copilot-instructions.md").write_text("# Copilot", "utf-8")

        source = ConfigSource(name="both", path=src_dir)
        load_source(source)

        assert source.instructions is not None
        assert ".copilot" in str(source.instructions)

    def test_missing_path(self, tmp_path: Path):
        source = ConfigSource(name="gone", path=tmp_path / "nonexistent")
        load_source(source)
        assert source.servers == {}
        assert source.instructions is None

    def test_loads_plugins_from_plugins_json(self, tmp_path: Path):
        """Committed plugins.json defines plugins to install."""
        src_dir = tmp_path / "work"
        copilot = src_dir / ".copilot"
        copilot.mkdir(parents=True)
        _write_json(
            copilot / "plugins.json",
            {"plugins": {"msx-mcp": {"source": "mcaps-microsoft/MSX-MCP"}}},
        )

        source = ConfigSource(name="work", path=src_dir)
        load_source(source)

        assert "msx-mcp" in source.plugins
        assert source.plugins["msx-mcp"]["source"] == "mcaps-microsoft/MSX-MCP"

    def test_local_json_merges_into_plugins_json(self, tmp_path: Path):
        """local.json plugins merge with (not replace) plugins.json."""
        src_dir = tmp_path / "work"
        copilot = src_dir / ".copilot"
        copilot.mkdir(parents=True)
        _write_json(
            copilot / "plugins.json",
            {"plugins": {"msx-mcp": {"source": "mcaps-microsoft/MSX-MCP"}}},
        )
        _write_json(
            copilot / "local.json",
            {"plugins": {"my-local": {"source": "me/my-plugin"}}, "paths": {"msx-mcp": "~/repos/msx-mcp"}},
        )

        source = ConfigSource(name="work", path=src_dir)
        load_source(source)

        assert "msx-mcp" in source.plugins
        assert "my-local" in source.plugins
        assert source.local_paths.get("msx-mcp") == "~/repos/msx-mcp"

    def test_local_json_plugins_without_plugins_json(self, tmp_path: Path):
        """local.json plugins still work when no plugins.json exists (backward compat)."""
        src_dir = tmp_path / "legacy"
        copilot = src_dir / ".copilot"
        copilot.mkdir(parents=True)
        _write_json(
            copilot / "local.json",
            {"plugins": {"my-plugin": {"source": "me/my-plugin"}}},
        )

        source = ConfigSource(name="legacy", path=src_dir)
        load_source(source)

        assert "my-plugin" in source.plugins

    def test_disabled_by_default_flag(self, tmp_path: Path):
        """Servers with disabledByDefault: true are tracked and field is stripped."""
        src_dir = tmp_path / "work"
        copilot = src_dir / ".copilot"
        copilot.mkdir(parents=True)
        _write_json(
            copilot / "mcp.json",
            {
                "mcpServers": {
                    "always-on": {"command": "npx", "args": ["--always"]},
                    "opt-in": {"url": "https://example.com", "disabledByDefault": True},
                    "also-on": {"command": "node", "args": ["server.js"]},
                }
            },
        )

        source = ConfigSource(name="work", path=src_dir)
        load_source(source)

        assert len(source.servers) == 3
        assert source.disabled_by_default == {"opt-in"}
        # disabledByDefault should be stripped from the entry itself
        assert "disabledByDefault" not in source.servers["opt-in"]
        assert "disabledByDefault" not in source.servers["always-on"]

    def test_auto_detects_plugin_json(self, tmp_path: Path):
        """plugin.json in .copilot/ auto-sets as_plugin."""
        src_dir = tmp_path / "personal"
        copilot = src_dir / ".copilot"
        copilot.mkdir(parents=True)
        _write_json(copilot / "plugin.json", {"name": "copilot-config", "version": "1.0.0"})

        source = ConfigSource(name="personal", path=src_dir)
        load_source(source)

        assert source.as_plugin is not None
        assert source.as_plugin["name"] == "copilot-config"

    def test_plugin_json_uses_source_name_fallback(self, tmp_path: Path):
        """plugin.json without a name falls back to source name."""
        src_dir = tmp_path / "personal"
        copilot = src_dir / ".copilot"
        copilot.mkdir(parents=True)
        _write_json(copilot / "plugin.json", {"version": "1.0.0"})

        source = ConfigSource(name="my-source", path=src_dir)
        load_source(source)

        assert source.as_plugin is not None
        assert source.as_plugin["name"] == "my-source"

    def test_local_json_as_plugin_overrides_plugin_json(self, tmp_path: Path):
        """Explicit asPlugin in local.json takes precedence over plugin.json."""
        src_dir = tmp_path / "work"
        copilot = src_dir / ".copilot"
        copilot.mkdir(parents=True)
        _write_json(copilot / "plugin.json", {"name": "copilot-config", "version": "1.0.0"})
        _write_json(copilot / "local.json", {"asPlugin": {"name": "custom-name"}})

        source = ConfigSource(name="work", path=src_dir)
        load_source(source)

        assert source.as_plugin["name"] == "custom-name"

    def test_no_plugin_json_no_as_plugin(self, tmp_path: Path):
        """Without plugin.json or local.json asPlugin, as_plugin stays None."""
        src_dir = tmp_path / "plain"
        copilot = src_dir / ".copilot"
        copilot.mkdir(parents=True)
        _write_json(copilot / "mcp.json", {"mcpServers": {"srv": {"command": "node"}}})

        source = ConfigSource(name="plain", path=src_dir)
        load_source(source)

        assert source.as_plugin is None

    def test_root_level_plugin_json_does_not_enable_as_plugin(self, tmp_path: Path):
        """A root-level plugin.json should not auto-set as_plugin."""
        src_dir = tmp_path / "npm-project"
        copilot = src_dir / ".copilot"
        copilot.mkdir(parents=True)
        # Root-level plugin.json (e.g. npm package) — should be ignored
        _write_json(src_dir / "plugin.json", {"name": "root-plugin", "version": "1.0.0"})
        _write_json(copilot / "mcp.json", {"mcpServers": {"srv": {"command": "node"}}})

        source = ConfigSource(name="npm-project", path=src_dir)
        load_source(source)

        assert source.as_plugin is None

    def test_plugin_json_null_name_falls_back(self, tmp_path: Path):
        """plugin.json with null/empty name falls back to source name."""
        src_dir = tmp_path / "personal"
        copilot = src_dir / ".copilot"
        copilot.mkdir(parents=True)
        _write_json(copilot / "plugin.json", {"name": None, "version": "1.0.0"})

        source = ConfigSource(name="my-source", path=src_dir)
        load_source(source)

        assert source.as_plugin is not None
        assert source.as_plugin["name"] == "my-source"


class TestMergeSources:
    def test_additive_servers(self, tmp_path: Path):
        s1 = ConfigSource(name="a", path=tmp_path)
        s1.servers = {"srv1": {"command": "npx", "args": []}}
        s2 = ConfigSource(name="b", path=tmp_path)
        s2.servers = {"srv2": {"url": "https://example.com"}}

        merged = merge_sources([s1, s2])
        assert len(merged.servers) == 2
        assert set(merged.servers.keys()) == {"srv1", "srv2"}

    def test_deduplicates_servers(self, tmp_path: Path):
        s1 = ConfigSource(name="a", path=tmp_path)
        s1.servers = {"dup": {"command": "npx", "args": [], "version": "1"}}
        s2 = ConfigSource(name="b", path=tmp_path)
        s2.servers = {"dup": {"command": "npx", "args": [], "version": "2"}}

        merged = merge_sources([s1, s2])
        assert len(merged.servers) == 1
        assert merged.servers["dup"]["version"] == "1"  # first wins

    def test_additive_skills(self, tmp_path: Path):
        d1 = tmp_path / "a" / "skills"
        d1.mkdir(parents=True)
        d2 = tmp_path / "b" / "skills"
        d2.mkdir(parents=True)

        s1 = ConfigSource(name="a", path=tmp_path / "a")
        s1.skill_dirs = [d1]
        s2 = ConfigSource(name="b", path=tmp_path / "b")
        s2.skill_dirs = [d2]

        merged = merge_sources([s1, s2])
        assert len(merged.skill_dirs) == 2

    def test_first_wins_instructions(self, tmp_path: Path):
        f1 = tmp_path / "a" / "copilot-instructions.md"
        f1.parent.mkdir(parents=True)
        f1.write_text("First", "utf-8")
        f2 = tmp_path / "b" / "copilot-instructions.md"
        f2.parent.mkdir(parents=True)
        f2.write_text("Second", "utf-8")

        s1 = ConfigSource(name="a", path=tmp_path / "a")
        s1.instructions = f1
        s2 = ConfigSource(name="b", path=tmp_path / "b")
        s2.instructions = f2

        merged = merge_sources([s1, s2])
        assert merged.instructions == f1  # first wins

    def test_first_wins_lsp(self, tmp_path: Path):
        s1 = ConfigSource(name="a", path=tmp_path)
        s1.lsp_servers = {"servers": [{"lang": "ts"}]}
        s2 = ConfigSource(name="b", path=tmp_path)
        s2.lsp_servers = {"servers": [{"lang": "py"}]}

        merged = merge_sources([s1, s2])
        assert merged.lsp_servers == s1.lsp_servers

    def test_empty_sources(self):
        merged = merge_sources([])
        assert merged.servers == {}
        assert merged.skill_dirs == []
        assert merged.instructions is None
        assert merged.disabled_by_default == set()

    def test_additive_plugins(self, tmp_path: Path):
        s1 = ConfigSource(name="a", path=tmp_path)
        s1.plugins = {"plug-a": {"source": "owner/a"}}
        s2 = ConfigSource(name="b", path=tmp_path)
        s2.plugins = {"plug-b": {"source": "owner/b"}}

        merged = merge_sources([s1, s2])
        assert len(merged.plugins) == 2
        assert "plug-a" in merged.plugins
        assert "plug-b" in merged.plugins

    def test_deduplicates_plugins(self, tmp_path: Path):
        s1 = ConfigSource(name="a", path=tmp_path)
        s1.plugins = {"dup": {"source": "owner/first"}}
        s2 = ConfigSource(name="b", path=tmp_path)
        s2.plugins = {"dup": {"source": "owner/second"}}

        merged = merge_sources([s1, s2])
        assert len(merged.plugins) == 1
        assert merged.plugins["dup"]["source"] == "owner/first"

    def test_disabled_by_default_merged(self, tmp_path: Path):
        """Disabled-by-default flags are unioned across sources."""
        s1 = ConfigSource(name="a", path=tmp_path)
        s1.servers = {"srv1": {"command": "npx"}, "srv2": {"url": "https://example.com"}}
        s1.disabled_by_default = {"srv2"}

        s2 = ConfigSource(name="b", path=tmp_path)
        s2.servers = {"srv3": {"command": "node"}}
        s2.disabled_by_default = {"srv3"}

        merged = merge_sources([s1, s2])
        assert merged.disabled_by_default == {"srv2", "srv3"}
        # All servers are still in merged.servers (filtering happens in cli.py)
        assert set(merged.servers.keys()) == {"srv1", "srv2", "srv3"}

    def test_as_plugin_excludes_skill_dirs(self, tmp_path: Path):
        """Sources with as_plugin route skills into source_plugins, not skill_dirs."""
        # Source with as_plugin — skills go to source_plugins
        d_work = tmp_path / "work" / ".copilot" / "skills"
        d_work.mkdir(parents=True)

        s_work = ConfigSource(name="work", path=tmp_path / "work")
        s_work.skill_dirs = [d_work]
        s_work.as_plugin = {"name": "copilot-config-work"}

        # Source without as_plugin — skills go to skill_dirs normally
        d_personal = tmp_path / "personal" / ".copilot" / "skills"
        d_personal.mkdir(parents=True)

        s_personal = ConfigSource(name="personal", path=tmp_path / "personal")
        s_personal.skill_dirs = [d_personal]

        merged = merge_sources([s_work, s_personal])

        # work skills excluded from skill_dirs
        assert len(merged.skill_dirs) == 1
        assert merged.skill_dirs[0] == d_personal

        # work skills registered as source plugin
        assert len(merged.source_plugins) == 1
        assert merged.source_plugins[0]["name"] == "copilot-config-work"
        plugin_path = merged.source_plugins[0]["path"]
        assert plugin_path == str(tmp_path / "work" / ".copilot")

    def test_as_plugin_still_excluded(self, tmp_path: Path):
        """Source with as_plugin still routes through source_plugins."""
        d = tmp_path / "personal" / ".copilot" / "skills"
        d.mkdir(parents=True)

        s = ConfigSource(name="personal", path=tmp_path / "personal")
        s.skill_dirs = [d]
        s.as_plugin = {"name": "copilot-config"}

        merged = merge_sources([s])

        assert merged.skill_dirs == []
        assert len(merged.source_plugins) == 1
        assert merged.source_plugins[0]["name"] == "copilot-config"
