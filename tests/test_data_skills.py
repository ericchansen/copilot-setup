"""Tests for copilotsetup.data.skills — skill directory scanning."""

from __future__ import annotations

from copilotsetup.data.skills import SkillInfo, SkillProvider


def test_returns_empty_when_dir_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    items = SkillProvider().load()
    assert items == []


def test_scans_real_directories(monkeypatch, tmp_path):
    skills = tmp_path / "skills"
    skills.mkdir()
    (skills / "my-skill").mkdir()
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    items = SkillProvider().load()
    assert len(items) == 1
    assert items[0].name == "my-skill"
    assert items[0].is_real_dir is True
    assert items[0].source == "local"


def test_items_are_frozen():
    info = SkillInfo(name="x")
    try:
        info.name = "y"  # type: ignore[misc]
        assert False, "Should have raised FrozenInstanceError"
    except AttributeError:
        pass


def test_status_enabled_for_real_dir():
    info = SkillInfo(name="s", is_real_dir=True)
    assert info.status == "enabled"
    assert info.reason == ""


def test_status_enabled_for_linked_ok():
    info = SkillInfo(name="s", is_linked=True, link_ok=True)
    assert info.status == "enabled"
    assert info.reason == ""


def test_status_broken_for_linked_not_ok():
    info = SkillInfo(name="s", is_linked=True, link_ok=False)
    assert info.status == "broken"
    assert info.reason == "dangling link"


def test_status_missing_for_neither():
    info = SkillInfo(name="s")
    assert info.status == "missing"
    assert info.reason == ""


def test_skips_files(monkeypatch, tmp_path):
    """Files (not dirs/links) in the skills dir are still reported."""
    skills = tmp_path / "skills"
    skills.mkdir()
    (skills / "not-a-dir.txt").write_text("hi")
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    items = SkillProvider().load()
    # The file entry is scanned; it's neither linked nor a dir → status missing
    assert len(items) == 1
    assert items[0].name == "not-a-dir.txt"
    assert items[0].status == "missing"


def test_sorted_order(monkeypatch, tmp_path):
    skills = tmp_path / "skills"
    skills.mkdir()
    (skills / "beta").mkdir()
    (skills / "alpha").mkdir()
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    items = SkillProvider().load()
    assert [i.name for i in items] == ["alpha", "beta"]


def test_symlink_resolved(monkeypatch, tmp_path):
    """Symlink pointing to a real directory is detected as linked + ok."""
    skills = tmp_path / "skills"
    skills.mkdir()
    target = tmp_path / "target-dir"
    target.mkdir()
    link = skills / "linked-skill"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        # On Windows without developer mode, symlinks may fail — skip test
        return
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    items = SkillProvider().load()
    assert len(items) == 1
    assert items[0].is_linked is True
    assert items[0].link_ok is True
    assert items[0].status == "enabled"
