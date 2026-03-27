"""Tests for copilotsetup/init.py — interactive onboarding wizard."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from copilotsetup.init import (
    _load_existing,
    _register_source,
    _scaffold_source,
    run_init,
)
from copilotsetup.ui import UI


def _make_ui() -> UI:
    return UI(["Init"])


class TestRegisterSource:
    def test_creates_new_file(self, tmp_path: Path):
        sf = tmp_path / "config-sources.json"
        _register_source(sf, "personal", "~/repos/copilot-config")

        data = json.loads(sf.read_text("utf-8"))
        assert len(data) == 1
        assert data[0]["name"] == "personal"
        assert data[0]["path"] == "~/repos/copilot-config"

    def test_appends_to_existing(self, tmp_path: Path):
        sf = tmp_path / "config-sources.json"
        sf.write_text(json.dumps([{"name": "work", "path": "~/work"}]), "utf-8")

        _register_source(sf, "personal", "~/repos/copilot-config")

        data = json.loads(sf.read_text("utf-8"))
        assert len(data) == 2
        assert data[0]["name"] == "work"
        assert data[1]["name"] == "personal"

    def test_creates_parent_dirs(self, tmp_path: Path):
        sf = tmp_path / "deeply" / "nested" / "config-sources.json"
        _register_source(sf, "test", "~/test")
        assert sf.exists()


class TestScaffoldSource:
    def test_creates_copilot_dir_with_files(self, tmp_path: Path):
        copilot_dir = tmp_path / "my-config" / ".copilot"
        result = _scaffold_source(copilot_dir)

        assert result is True
        assert copilot_dir.is_dir()
        assert (copilot_dir / "mcp.json").is_file()
        assert (copilot_dir / "copilot-instructions.md").is_file()
        assert (copilot_dir / "local.json").is_file()
        assert (copilot_dir / "skills").is_dir()

    def test_mcp_json_is_valid(self, tmp_path: Path):
        copilot_dir = tmp_path / ".copilot"
        _scaffold_source(copilot_dir)

        data = json.loads((copilot_dir / "mcp.json").read_text("utf-8"))
        assert "mcpServers" in data

    def test_does_not_overwrite_existing(self, tmp_path: Path):
        copilot_dir = tmp_path / ".copilot"
        copilot_dir.mkdir()
        (copilot_dir / "mcp.json").write_text('{"mcpServers": {"existing": {}}}', "utf-8")

        _scaffold_source(copilot_dir)

        data = json.loads((copilot_dir / "mcp.json").read_text("utf-8"))
        assert "existing" in data["mcpServers"]


class TestLoadExisting:
    def test_loads_valid_file(self, tmp_path: Path):
        sf = tmp_path / "config-sources.json"
        sf.write_text(json.dumps([{"name": "a", "path": "/a"}]), "utf-8")
        assert len(_load_existing(sf)) == 1

    def test_returns_empty_on_missing_file(self, tmp_path: Path):
        sf = tmp_path / "nonexistent.json"
        assert _load_existing(sf) == []

    def test_returns_empty_on_invalid_json(self, tmp_path: Path):
        sf = tmp_path / "bad.json"
        sf.write_text("not json", "utf-8")
        assert _load_existing(sf) == []


class TestRunInit:
    def test_non_interactive_no_sources(self, tmp_path: Path):
        """Non-interactive mode exits early when no sources exist."""
        ui = _make_ui()
        with patch("copilotsetup.init.sources_file", return_value=tmp_path / "cs.json"):
            result = run_init(ui, non_interactive=True)
        assert result is False

    def test_interactive_registers_source(self, tmp_path: Path):
        """Interactive mode creates config-sources.json and scaffolds."""
        sf = tmp_path / "config-sources.json"
        source_dir = tmp_path / "my-config"
        ui = _make_ui()

        # Simulate user input: name=personal, path=source_dir, yes to create, yes to scaffold
        with (
            patch("copilotsetup.init.sources_file", return_value=sf),
            patch.object(ui, "prompt", side_effect=["personal", str(source_dir)]),
            patch.object(ui, "confirm", return_value=True),
        ):
            result = run_init(ui)

        assert result is True
        assert sf.exists()
        data = json.loads(sf.read_text("utf-8"))
        assert data[0]["name"] == "personal"
        assert (source_dir / ".copilot" / "mcp.json").is_file()

    def test_interactive_skip_scaffold(self, tmp_path: Path):
        """User can decline scaffolding."""
        sf = tmp_path / "config-sources.json"
        source_dir = tmp_path / "existing"
        source_dir.mkdir()
        ui = _make_ui()

        with (
            patch("copilotsetup.init.sources_file", return_value=sf),
            patch.object(ui, "prompt", side_effect=["work", str(source_dir)]),
            patch.object(ui, "confirm", return_value=False),
        ):
            result = run_init(ui)

        assert result is True
        assert sf.exists()
        assert not (source_dir / ".copilot").exists()

    def test_aborts_on_empty_name(self, tmp_path: Path):
        """Empty name aborts the wizard."""
        sf = tmp_path / "config-sources.json"
        ui = _make_ui()

        with (
            patch("copilotsetup.init.sources_file", return_value=sf),
            patch.object(ui, "prompt", return_value=""),
        ):
            result = run_init(ui)

        assert result is False
        assert not sf.exists()
