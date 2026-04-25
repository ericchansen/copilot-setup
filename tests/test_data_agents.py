"""Tests for copilotsetup.data.agents — agent file scanning."""

from __future__ import annotations

from copilotsetup.data.agents import AgentInfo, AgentProvider


def test_returns_empty_when_dir_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    items = AgentProvider().load()
    assert items == []


def test_reads_agent_files(monkeypatch, tmp_path):
    agents = tmp_path / "agents"
    agents.mkdir()
    (agents / "helper.agent.md").write_text("This is my helper agent\nMore detail.", encoding="utf-8")
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    items = AgentProvider().load()
    assert len(items) == 1
    assert items[0].name == "helper"
    assert items[0].description == "This is my helper agent"


def test_skips_non_agent_md_files(monkeypatch, tmp_path):
    agents = tmp_path / "agents"
    agents.mkdir()
    (agents / "readme.md").write_text("not an agent")
    (agents / "notes.txt").write_text("random")
    (agents / "real.agent.md").write_text("I am real")
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    items = AgentProvider().load()
    assert len(items) == 1
    assert items[0].name == "real"


def test_items_are_frozen():
    info = AgentInfo(name="x")
    try:
        info.name = "y"  # type: ignore[misc]
        assert False, "Should have raised FrozenInstanceError"
    except AttributeError:
        pass


def test_description_skips_blank_lines(monkeypatch, tmp_path):
    agents = tmp_path / "agents"
    agents.mkdir()
    (agents / "blank.agent.md").write_text("\n\n  \nActual first line", encoding="utf-8")
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    items = AgentProvider().load()
    assert items[0].description == "Actual first line"


def test_description_truncated_at_120(monkeypatch, tmp_path):
    agents = tmp_path / "agents"
    agents.mkdir()
    long_line = "A" * 200
    (agents / "long.agent.md").write_text(long_line, encoding="utf-8")
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    items = AgentProvider().load()
    assert len(items[0].description) == 120


def test_sorted_order(monkeypatch, tmp_path):
    agents = tmp_path / "agents"
    agents.mkdir()
    (agents / "zeta.agent.md").write_text("Z agent")
    (agents / "alpha.agent.md").write_text("A agent")
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    items = AgentProvider().load()
    assert [i.name for i in items] == ["alpha", "zeta"]


def test_empty_file_has_no_description(monkeypatch, tmp_path):
    agents = tmp_path / "agents"
    agents.mkdir()
    (agents / "empty.agent.md").write_text("", encoding="utf-8")
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    items = AgentProvider().load()
    assert items[0].description == ""


def test_skips_directories(monkeypatch, tmp_path):
    """Directories (even with .agent.md name) should be skipped."""
    agents = tmp_path / "agents"
    agents.mkdir()
    (agents / "dir.agent.md").mkdir()
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    items = AgentProvider().load()
    assert items == []
