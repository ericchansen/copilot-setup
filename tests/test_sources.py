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
        _write_json(copilot / "mcp.json", {
            "mcpServers": {
                "azure-mcp": {"command": "npx", "args": ["-y", "@azure/mcp@latest"]},
                "context7": {"url": "https://mcp.context7.com/mcp"},
            }
        })

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
