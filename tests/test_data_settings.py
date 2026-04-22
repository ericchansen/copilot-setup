"""Tests for copilotsetup.data.settings — user preferences loading."""

from __future__ import annotations

import json

from copilotsetup.data.settings import SettingInfo, SettingsProvider


def test_returns_empty_when_config_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    assert SettingsProvider().load() == []


def test_returns_empty_when_config_is_not_dict(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    (tmp_path / "config.json").write_text(json.dumps([1, 2, 3]))
    assert SettingsProvider().load() == []


def test_reads_simple_string_setting(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    cfg = {"theme": "dark"}
    (tmp_path / "config.json").write_text(json.dumps(cfg))
    items = SettingsProvider().load()
    assert len(items) == 1
    assert items[0].key == "theme"
    assert items[0].value == "dark"
    assert items[0].value_type == "string"


def test_reads_simple_bool_setting(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    cfg = {"telemetry": True}
    (tmp_path / "config.json").write_text(json.dumps(cfg))
    items = SettingsProvider().load()
    assert len(items) == 1
    assert items[0].key == "telemetry"
    assert items[0].value == "True"
    assert items[0].value_type == "bool"


def test_reads_numeric_setting(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    cfg = {"timeout": 30}
    (tmp_path / "config.json").write_text(json.dumps(cfg))
    items = SettingsProvider().load()
    assert len(items) == 1
    assert items[0].value == "30"
    assert items[0].value_type == "string"


def test_skips_keys_belonging_to_other_tabs(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    cfg = {
        "hooks": {"onStart": []},
        "installedPlugins": {"foo": {}},
        "mcpServers": {"bar": {}},
        "lspServers": {"baz": {}},
        "permissions": {},
        "networkPermissions": {},
        "commandPermissions": {},
        "enabledPlugins": [],
        "theme": "dark",
    }
    (tmp_path / "config.json").write_text(json.dumps(cfg))
    items = SettingsProvider().load()
    keys = [i.key for i in items]
    assert "theme" in keys
    assert "hooks" not in keys
    assert "installedPlugins" not in keys
    assert "mcpServers" not in keys
    assert "lspServers" not in keys
    assert "permissions" not in keys
    assert "networkPermissions" not in keys
    assert "commandPermissions" not in keys
    assert "enabledPlugins" not in keys


def test_flattens_one_level_of_nested_dicts(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    cfg = {
        "chat": {
            "enabled": True,
            "maxTokens": 4096,
        }
    }
    (tmp_path / "config.json").write_text(json.dumps(cfg))
    items = SettingsProvider().load()
    assert len(items) == 2
    keys = {i.key for i in items}
    assert keys == {"chat.enabled", "chat.maxTokens"}
    by_key = {i.key: i for i in items}
    assert by_key["chat.enabled"].value == "True"
    assert by_key["chat.enabled"].value_type == "bool"
    assert by_key["chat.maxTokens"].value == "4096"


def test_shows_nested_complex_values(tmp_path, monkeypatch):
    """Nested dicts and lists inside dicts are now shown with formatted values."""
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    cfg = {
        "chat": {
            "simple": "yes",
            "complex": {"deeply": "nested"},
            "also_complex": [1, 2, 3],
        }
    }
    (tmp_path / "config.json").write_text(json.dumps(cfg))
    items = SettingsProvider().load()
    by_key = {i.key: i for i in items}
    assert "chat.simple" in by_key
    assert "chat.complex" in by_key
    assert "chat.also_complex" in by_key
    assert by_key["chat.also_complex"].value_type == "list"


def test_shows_top_level_lists(tmp_path, monkeypatch):
    """Top-level lists are now shown as comma-separated values."""
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    cfg = {"simple": "yes", "complex_list": [1, 2], "theme": "light"}
    (tmp_path / "config.json").write_text(json.dumps(cfg))
    items = SettingsProvider().load()
    keys = [i.key for i in items]
    assert "simple" in keys
    assert "theme" in keys
    assert "complex_list" in keys


def test_items_are_frozen():
    info = SettingInfo(key="k", display_name="d", value="v")
    try:
        info.key = "changed"  # type: ignore[misc]
        raise AssertionError("Should have raised FrozenInstanceError")
    except AttributeError:
        pass


def test_status_property_enabled():
    info = SettingInfo(key="k", display_name="d", value="True", value_type="bool")
    assert info.status == "enabled"


def test_status_property_custom():
    info = SettingInfo(key="k", display_name="d", value="dark", value_type="string")
    assert info.status == "custom"


def test_results_sorted_by_key(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    cfg = {"zebra": "z", "alpha": "a", "middle": "m"}
    (tmp_path / "config.json").write_text(json.dumps(cfg))
    items = SettingsProvider().load()
    keys = [i.key for i in items]
    assert keys == sorted(keys)
