"""Tests for lib/sources.py — config source discovery, loading, and merging."""

from __future__ import annotations

import json
from pathlib import Path

from lib.sources import ConfigSource, load_source, merge_sources


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), "utf-8")


class TestLoadSource:
    def test_loads_servers(self, tmp_path: Path):
        src_dir = tmp_path / "personal"
        src_dir.mkdir()
        _write_json(src_dir / "mcp-servers.json", {
            "servers": [
                {"name": "azure-mcp", "category": "base", "type": "npx"},
                {"name": "context7", "type": "http"},
            ]
        })

        source = ConfigSource(name="personal", path=src_dir)
        load_source(source)

        assert len(source.servers) == 2
        # Category field should be stripped
        assert "category" not in source.servers[0]
        assert source.servers[0]["name"] == "azure-mcp"

    def test_loads_plugins(self, tmp_path: Path):
        src_dir = tmp_path / "work"
        src_dir.mkdir()
        _write_json(src_dir / "plugins.json", {
            "plugins": [{"name": "msx-mcp", "source": "mcaps-microsoft/MSX-MCP"}]
        })

        source = ConfigSource(name="work", path=src_dir)
        load_source(source)

        assert len(source.plugins) == 1
        assert source.plugins[0]["name"] == "msx-mcp"

    def test_loads_instructions(self, tmp_path: Path):
        src_dir = tmp_path / "personal"
        src_dir.mkdir()
        (src_dir / "copilot-instructions.md").write_text("# Instructions", "utf-8")

        source = ConfigSource(name="personal", path=src_dir)
        load_source(source)

        assert source.instructions is not None
        assert source.instructions.name == "copilot-instructions.md"

    def test_loads_skills_dir(self, tmp_path: Path):
        src_dir = tmp_path / "personal"
        skills = src_dir / "skills" / "my-skill"
        skills.mkdir(parents=True)
        (skills / "SKILL.md").write_text("---\nname: my-skill\n---", "utf-8")

        source = ConfigSource(name="personal", path=src_dir)
        load_source(source)

        assert len(source.skill_dirs) == 1
        assert source.skill_dirs[0].name == "skills"

    def test_legacy_copilot_dir_fallback(self, tmp_path: Path):
        src_dir = tmp_path / "old-layout"
        src_dir.mkdir()
        legacy = src_dir / ".copilot"
        legacy.mkdir()
        (legacy / "copilot-instructions.md").write_text("# Legacy", "utf-8")

        skills = legacy / "skills" / "some-skill"
        skills.mkdir(parents=True)
        (skills / "SKILL.md").write_text("---\nname: some-skill\n---", "utf-8")

        source = ConfigSource(name="old", path=src_dir)
        load_source(source)

        assert source.instructions is not None
        assert ".copilot" in str(source.instructions)
        assert len(source.skill_dirs) == 1

    def test_missing_path(self, tmp_path: Path):
        source = ConfigSource(name="gone", path=tmp_path / "nonexistent")
        load_source(source)
        assert source.servers == []
        assert source.plugins == []
        assert source.instructions is None


class TestMergeSources:
    def test_additive_servers(self, tmp_path: Path):
        s1 = ConfigSource(name="a", path=tmp_path)
        s1.servers = [{"name": "srv1", "type": "npx"}]
        s2 = ConfigSource(name="b", path=tmp_path)
        s2.servers = [{"name": "srv2", "type": "http"}]

        merged = merge_sources([s1, s2])
        assert len(merged.servers) == 2
        assert {s["name"] for s in merged.servers} == {"srv1", "srv2"}

    def test_deduplicates_servers(self, tmp_path: Path):
        s1 = ConfigSource(name="a", path=tmp_path)
        s1.servers = [{"name": "dup", "type": "npx", "version": "1"}]
        s2 = ConfigSource(name="b", path=tmp_path)
        s2.servers = [{"name": "dup", "type": "npx", "version": "2"}]

        merged = merge_sources([s1, s2])
        assert len(merged.servers) == 1
        assert merged.servers[0]["version"] == "1"  # first wins

    def test_additive_plugins(self, tmp_path: Path):
        s1 = ConfigSource(name="a", path=tmp_path)
        s1.plugins = [{"name": "p1"}]
        s2 = ConfigSource(name="b", path=tmp_path)
        s2.plugins = [{"name": "p2"}]

        merged = merge_sources([s1, s2])
        assert len(merged.plugins) == 2

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
        assert merged.servers == []
        assert merged.plugins == []
        assert merged.skill_dirs == []
        assert merged.instructions is None
