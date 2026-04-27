"""Tests for copilotsetup.data.profiles — profile directory scanning."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

from copilotsetup.data.profiles import (
    ProfileInfo,
    ProfileProvider,
    _default_home,
    _scan_profile,
    create_profile,
    delete_profile,
    detect_active_profile,
    profile_server_matrix,
    rename_profile,
)


def test_empty_when_dir_missing(tmp_path):
    with patch.dict(os.environ, {"COPILOT_HOME": str(tmp_path)}):
        items = ProfileProvider().load()
    # Always includes (default) even with no profiles dir
    assert len(items) == 1
    assert items[0].name == "(default)"
    assert items[0].is_default is True


def test_reads_profiles_from_directory(tmp_path):
    prof_dir = tmp_path / "profiles"
    prof_dir.mkdir()
    (prof_dir / "work").mkdir()
    (prof_dir / "personal").mkdir()

    with patch.dict(os.environ, {"COPILOT_HOME": str(tmp_path)}):
        items = ProfileProvider().load()

    assert len(items) == 3  # (default) + personal + work
    names = [i.name for i in items]
    assert names == ["(default)", "personal", "work"]
    assert items[0].is_default is True
    assert items[1].is_default is False


def test_active_profile_detected(tmp_path):
    prof_dir = tmp_path / "profiles"
    prof_dir.mkdir()
    (prof_dir / "work").mkdir()
    (prof_dir / "personal").mkdir()

    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"activeProfile": "work"}), encoding="utf-8")

    with patch.dict(os.environ, {"COPILOT_HOME": str(tmp_path)}):
        items = ProfileProvider().load()

    by_name = {i.name: i for i in items}
    assert by_name["work"].active is True
    assert by_name["personal"].active is False
    assert by_name["(default)"].active is False  # not active when a profile is


def test_no_active_when_config_missing(tmp_path):
    prof_dir = tmp_path / "profiles"
    prof_dir.mkdir()
    (prof_dir / "default").mkdir()

    with patch.dict(os.environ, {"COPILOT_HOME": str(tmp_path)}):
        items = ProfileProvider().load()

    assert len(items) == 2  # (default) + default
    assert items[0].name == "(default)"
    assert items[0].active is True  # default is active when no activeProfile set
    assert items[1].active is False


def test_skips_files_in_profiles_dir(tmp_path):
    prof_dir = tmp_path / "profiles"
    prof_dir.mkdir()
    (prof_dir / "not-a-dir.txt").write_text("hi", encoding="utf-8")
    (prof_dir / "real-profile").mkdir()

    with patch.dict(os.environ, {"COPILOT_HOME": str(tmp_path)}):
        items = ProfileProvider().load()

    assert len(items) == 2  # (default) + real-profile
    assert items[1].name == "real-profile"


def test_items_are_frozen():
    info = ProfileInfo(name="test")
    try:
        info.name = "changed"  # type: ignore[misc]
        assert False, "Should have raised FrozenInstanceError"
    except AttributeError:
        pass


def test_path_is_populated(tmp_path):
    prof_dir = tmp_path / "profiles"
    prof_dir.mkdir()
    (prof_dir / "my-profile").mkdir()

    with patch.dict(os.environ, {"COPILOT_HOME": str(tmp_path)}):
        items = ProfileProvider().load()

    # items[0] is (default), items[1] is my-profile
    assert items[1].path == str(prof_dir / "my-profile")


# ── _scan_profile tests ──────────────────────────────────────────────────────


def test_scan_profile_all_files(tmp_path):
    """Profile with all config files populated."""
    (tmp_path / "mcp-config.json").write_text(
        json.dumps({"mcpServers": {"server-a": {}, "server-b": {}}}),
        encoding="utf-8",
    )
    (tmp_path / "config.json").write_text(
        json.dumps({"installedPlugins": [{"name": "plug-1"}, {"name": "plug-2"}]}),
        encoding="utf-8",
    )
    (tmp_path / "lsp-config.json").write_text(
        json.dumps({"lspServers": {"typescript": {}, "python": {}}}),
        encoding="utf-8",
    )
    (tmp_path / "settings.json").write_text(
        json.dumps({"model": "claude-opus-4.5"}),
        encoding="utf-8",
    )
    (tmp_path / "copilot-instructions.md").write_text("# Instructions", encoding="utf-8")
    sessions = tmp_path / "session-state"
    sessions.mkdir()
    (sessions / "session-1").mkdir()
    (sessions / "session-2").mkdir()

    result = _scan_profile(tmp_path)
    assert result["mcp_servers"] == ("server-a", "server-b")
    assert result["plugins"] == ("plug-1", "plug-2")
    assert result["lsp_servers"] == ("python", "typescript")
    assert result["model"] == "claude-opus-4.5"
    assert result["has_instructions"] is True
    assert result["session_count"] == 2


def test_scan_profile_empty_dir(tmp_path):
    """Profile with no config files at all."""
    result = _scan_profile(tmp_path)
    assert result["mcp_servers"] == ()
    assert result["plugins"] == ()
    assert result["lsp_servers"] == ()
    assert result["model"] == ""
    assert result["has_instructions"] is False
    assert result["session_count"] == 0


def test_scan_profile_partial_files(tmp_path):
    """Profile with only mcp-config.json."""
    (tmp_path / "mcp-config.json").write_text(
        json.dumps({"mcpServers": {"only-server": {}}}),
        encoding="utf-8",
    )
    result = _scan_profile(tmp_path)
    assert result["mcp_servers"] == ("only-server",)
    assert result["plugins"] == ()
    assert result["model"] == ""


def test_scan_profile_malformed_json(tmp_path):
    """Malformed JSON files should not crash."""
    (tmp_path / "mcp-config.json").write_text("not json", encoding="utf-8")
    (tmp_path / "config.json").write_text("{bad", encoding="utf-8")
    result = _scan_profile(tmp_path)
    assert result["mcp_servers"] == ()
    assert result["plugins"] == ()


def test_scan_profile_skips_invalid_plugin_entries(tmp_path):
    """Plugin entries without name or non-dict entries are skipped."""
    (tmp_path / "config.json").write_text(
        json.dumps({"installedPlugins": [{"name": "good"}, "bad", {"version": "1.0"}, None]}),
        encoding="utf-8",
    )
    result = _scan_profile(tmp_path)
    assert result["plugins"] == ("good",)


def test_load_includes_scan_data(tmp_path):
    """ProfileProvider.load() populates the expanded fields."""
    prof_dir = tmp_path / "profiles"
    work = prof_dir / "work"
    work.mkdir(parents=True)
    (work / "mcp-config.json").write_text(
        json.dumps({"mcpServers": {"teams": {}}}),
        encoding="utf-8",
    )
    (work / "settings.json").write_text(
        json.dumps({"model": "gpt-5-mini"}),
        encoding="utf-8",
    )

    with patch.dict(os.environ, {"COPILOT_HOME": str(tmp_path)}):
        items = ProfileProvider().load()

    # (default) + work
    assert len(items) == 2
    work_item = items[1]
    assert work_item.name == "work"
    assert work_item.mcp_servers == ("teams",)
    assert work_item.model == "gpt-5-mini"


# ── detect_active_profile tests ──────────────────────────────────────────────


def test_detect_active_profile_when_set(tmp_path, monkeypatch):
    prof_dir = tmp_path / ".copilot" / "profiles" / "work"
    prof_dir.mkdir(parents=True)
    monkeypatch.setenv("COPILOT_HOME", str(prof_dir))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    result = detect_active_profile()
    assert result == "work"


def test_detect_active_profile_when_unset(monkeypatch):
    monkeypatch.delenv("COPILOT_HOME", raising=False)
    result = detect_active_profile()
    assert result == ""


def test_detect_active_profile_when_root(tmp_path, monkeypatch):
    copilot_dir = tmp_path / ".copilot"
    copilot_dir.mkdir()
    monkeypatch.setenv("COPILOT_HOME", str(copilot_dir))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    result = detect_active_profile()
    assert result == ""


# ── _default_home tests ──────────────────────────────────────────────────────


def test_default_home_returns_root_when_not_overridden(tmp_path, monkeypatch):
    """When COPILOT_HOME is the root, _default_home() returns it as-is."""
    copilot_dir = tmp_path / ".copilot"
    copilot_dir.mkdir()
    monkeypatch.setenv("COPILOT_HOME", str(copilot_dir))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    assert _default_home() == copilot_dir


def test_default_home_escapes_profile_override(tmp_path, monkeypatch):
    """When COPILOT_HOME points inside profiles/, _default_home() returns root."""
    root = tmp_path / ".copilot"
    profile = root / "profiles" / "work"
    profile.mkdir(parents=True)
    monkeypatch.setenv("COPILOT_HOME", str(profile))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    assert _default_home() == root


def test_default_home_with_arbitrary_path(tmp_path, monkeypatch):
    """When COPILOT_HOME is an arbitrary path, _default_home() returns it."""
    custom = tmp_path / "my-copilot"
    custom.mkdir()
    monkeypatch.setenv("COPILOT_HOME", str(custom))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    assert _default_home() == custom


def test_load_still_shows_all_profiles_while_browsing(tmp_path, monkeypatch):
    """ProfileProvider.load() shows all profiles even when COPILOT_HOME is overridden."""
    root = tmp_path / ".copilot"
    (root / "profiles" / "work").mkdir(parents=True)
    (root / "profiles" / "dev").mkdir()
    # Simulate browsing the "work" profile
    monkeypatch.setenv("COPILOT_HOME", str(root / "profiles" / "work"))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

    items = ProfileProvider().load()
    names = [i.name for i in items]
    assert "(default)" in names
    assert "work" in names
    assert "dev" in names
    # (default) should point to root, not the profile
    default = next(i for i in items if i.is_default)
    assert default.path == str(root)


# ── profile_server_matrix tests ──────────────────────────────────────────────


def test_profile_server_matrix(tmp_path):
    prof_dir = tmp_path / "profiles"
    work = prof_dir / "work"
    work.mkdir(parents=True)
    (work / "mcp-config.json").write_text(
        json.dumps({"mcpServers": {"teams": {}, "outlook": {}}}),
        encoding="utf-8",
    )
    dev = prof_dir / "dev"
    dev.mkdir()
    (dev / "mcp-config.json").write_text(
        json.dumps({"mcpServers": {"playwright": {}, "teams": {}}}),
        encoding="utf-8",
    )

    with patch.dict(os.environ, {"COPILOT_HOME": str(tmp_path)}):
        matrix = profile_server_matrix()

    assert matrix["teams"] == {"work", "dev"}
    assert matrix["outlook"] == {"work"}
    assert matrix["playwright"] == {"dev"}


def test_profile_server_matrix_empty(tmp_path):
    with patch.dict(os.environ, {"COPILOT_HOME": str(tmp_path)}):
        matrix = profile_server_matrix()
    assert matrix == {}


# ── create_profile tests ─────────────────────────────────────────────────────


def test_create_profile_from_root(tmp_path):
    # Set up root with config files
    (tmp_path / "config.json").write_text(json.dumps({"installedPlugins": []}), encoding="utf-8")
    (tmp_path / "mcp-config.json").write_text(json.dumps({"mcpServers": {"s": {}}}), encoding="utf-8")
    (tmp_path / "settings.json").write_text(json.dumps({"model": "opus"}), encoding="utf-8")
    (tmp_path / "profiles").mkdir()

    with patch.dict(os.environ, {"COPILOT_HOME": str(tmp_path)}):
        path = create_profile("my-work")

    assert path.name == "my-work"
    assert (path / "config.json").is_file()
    assert (path / "mcp-config.json").is_file()
    assert (path / "settings.json").is_file()
    data = json.loads((path / "mcp-config.json").read_text(encoding="utf-8"))
    assert "s" in data["mcpServers"]


def test_create_profile_duplicate_raises(tmp_path):
    (tmp_path / "profiles" / "dupe").mkdir(parents=True)
    with patch.dict(os.environ, {"COPILOT_HOME": str(tmp_path)}):
        try:
            create_profile("dupe")
            assert False, "Should have raised FileExistsError"
        except FileExistsError:
            pass


def test_create_profile_invalid_name():
    try:
        create_profile("")
        assert False, "Should have raised ValueError"
    except ValueError:
        pass

    try:
        create_profile("bad/name")
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


def test_create_profile_from_another_profile(tmp_path):
    (tmp_path / "profiles").mkdir()
    source = tmp_path / "profiles" / "source"
    source.mkdir()
    (source / "mcp-config.json").write_text(json.dumps({"mcpServers": {"x": {}}}), encoding="utf-8")

    with patch.dict(os.environ, {"COPILOT_HOME": str(tmp_path)}):
        path = create_profile("cloned", source_path=source)

    assert (path / "mcp-config.json").is_file()
    data = json.loads((path / "mcp-config.json").read_text(encoding="utf-8"))
    assert "x" in data["mcpServers"]


# ── delete_profile tests ─────────────────────────────────────────────────────


def test_delete_profile(tmp_path):
    prof_dir = tmp_path / "profiles" / "deleteme"
    prof_dir.mkdir(parents=True)
    (prof_dir / "config.json").write_text("{}", encoding="utf-8")

    with patch.dict(os.environ, {"COPILOT_HOME": str(tmp_path)}):
        result = delete_profile("deleteme")

    assert result is True
    assert not prof_dir.exists()


def test_delete_profile_not_found(tmp_path):
    (tmp_path / "profiles").mkdir()
    with patch.dict(os.environ, {"COPILOT_HOME": str(tmp_path)}):
        result = delete_profile("nonexistent")
    assert result is False


def test_delete_profile_invalid_name():
    try:
        delete_profile("")
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


# ── rename_profile tests ─────────────────────────────────────────────────────


def test_rename_profile(tmp_path):
    prof_dir = tmp_path / "profiles" / "old-name"
    prof_dir.mkdir(parents=True)
    (prof_dir / "config.json").write_text("{}", encoding="utf-8")

    with patch.dict(os.environ, {"COPILOT_HOME": str(tmp_path)}):
        new_path = rename_profile("old-name", "new-name")

    assert new_path.name == "new-name"
    assert not prof_dir.exists()
    assert (tmp_path / "profiles" / "new-name" / "config.json").is_file()


def test_rename_profile_duplicate_raises(tmp_path):
    profs = tmp_path / "profiles"
    (profs / "a").mkdir(parents=True)
    (profs / "b").mkdir()

    with patch.dict(os.environ, {"COPILOT_HOME": str(tmp_path)}):
        try:
            rename_profile("a", "b")
            assert False, "Should have raised FileExistsError"
        except FileExistsError:
            pass


def test_rename_profile_not_found(tmp_path):
    (tmp_path / "profiles").mkdir()
    with patch.dict(os.environ, {"COPILOT_HOME": str(tmp_path)}):
        try:
            rename_profile("nonexistent", "new")
            assert False, "Should have raised FileNotFoundError"
        except FileNotFoundError:
            pass


def test_rename_profile_invalid_name():
    try:
        rename_profile("", "new")
        assert False, "Should have raised ValueError"
    except ValueError:
        pass

    try:
        rename_profile("old", "bad/name")
        assert False, "Should have raised ValueError"
    except ValueError:
        pass
