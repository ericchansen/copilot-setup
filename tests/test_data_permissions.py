"""Tests for copilotsetup.data.permissions — permission config loading."""

from __future__ import annotations

import json

from copilotsetup.data.permissions import PermissionEntry, PermissionProvider


def test_returns_empty_when_config_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    assert PermissionProvider().load() == []


def test_returns_empty_when_keys_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    (tmp_path / "config.json").write_text(json.dumps({"other": 1}))
    assert PermissionProvider().load() == []


def test_loads_all_categories(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    cfg = {
        "trustedFolders": ["/home/user/project"],
        "allowedUrls": ["https://example.com"],
        "deniedUrls": ["https://evil.com"],
    }
    (tmp_path / "config.json").write_text(json.dumps(cfg))
    items = PermissionProvider().load()
    assert len(items) == 3
    categories = {i.category for i in items}
    assert categories == {"trustedFolders", "allowedUrls", "deniedUrls"}


def test_skips_empty_strings(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    cfg = {"trustedFolders": ["", "/valid"]}
    (tmp_path / "config.json").write_text(json.dumps(cfg))
    items = PermissionProvider().load()
    assert len(items) == 1
    assert items[0].value == "/valid"


def test_skips_non_string_values(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    cfg = {"allowedUrls": [42, None, True, "https://ok.com"]}
    (tmp_path / "config.json").write_text(json.dumps(cfg))
    items = PermissionProvider().load()
    assert len(items) == 1
    assert items[0].value == "https://ok.com"


def test_skips_non_list_category(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    cfg = {"trustedFolders": "not-a-list"}
    (tmp_path / "config.json").write_text(json.dumps(cfg))
    assert PermissionProvider().load() == []


def test_items_are_frozen():
    entry = PermissionEntry(category="trustedFolders", value="/path")
    try:
        entry.category = "changed"  # type: ignore[misc]
        raise AssertionError("Should have raised FrozenInstanceError")
    except AttributeError:
        pass


def test_multiple_values_in_single_category(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    cfg = {"trustedFolders": ["/a", "/b", "/c"]}
    (tmp_path / "config.json").write_text(json.dumps(cfg))
    items = PermissionProvider().load()
    assert len(items) == 3
    assert all(i.category == "trustedFolders" for i in items)
