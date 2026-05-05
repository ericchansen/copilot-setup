"""Tests for copilotsetup.data.plugins — plugin config loading."""

from __future__ import annotations

import json

from copilotsetup.data.plugins import PluginInfo, PluginProvider, set_plugin_enabled


def test_returns_empty_when_config_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    assert PluginProvider().load() == []


def test_returns_empty_when_installed_plugins_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    (tmp_path / "config.json").write_text(json.dumps({"other": 1}))
    assert PluginProvider().load() == []


def test_parses_plugin_entries(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    cfg = {
        "installedPlugins": [
            {
                "name": "msx-mcp",
                "version": "1.0.0",
                "marketplace": "copilot",
                "enabled": True,
            },
            {
                "name": "my-local-plugin",
                "version": "0.2.0",
            },
        ]
    }
    (tmp_path / "config.json").write_text(json.dumps(cfg))
    items = PluginProvider().load()
    assert len(items) == 2
    assert items[0].name == "msx-mcp"
    assert items[0].source == "copilot"
    assert items[0].version == "1.0.0"
    assert items[0].installed is True
    assert items[0].disabled is False
    assert items[1].name == "my-local-plugin"
    assert items[1].source == "local"


def test_disabled_from_enabled_plugins_map_name_key(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    cfg = {
        "installedPlugins": [{"name": "foo", "marketplace": "copilot"}],
        "enabledPlugins": {"foo": False},
    }
    (tmp_path / "config.json").write_text(json.dumps(cfg))
    items = PluginProvider().load()
    assert len(items) == 1
    assert items[0].disabled is True
    assert items[0].status == "disabled"


def test_disabled_from_enabled_plugins_map_name_at_marketplace(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    cfg = {
        "installedPlugins": [{"name": "bar", "marketplace": "copilot"}],
        "enabledPlugins": {"bar@copilot": False},
    }
    (tmp_path / "config.json").write_text(json.dumps(cfg))
    items = PluginProvider().load()
    assert items[0].disabled is True


def test_disabled_from_enabled_plugins_map_name_at_local(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    cfg = {
        "installedPlugins": [{"name": "baz", "marketplace": "copilot"}],
        "enabledPlugins": {"baz@local": False},
    }
    (tmp_path / "config.json").write_text(json.dumps(cfg))
    items = PluginProvider().load()
    assert items[0].disabled is True


def test_enabled_plugins_map_true_overrides_entry_false(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    cfg = {
        "installedPlugins": [{"name": "re-enabled", "marketplace": "copilot", "enabled": False}],
        "enabledPlugins": {"re-enabled": True},
    }
    (tmp_path / "config.json").write_text(json.dumps(cfg))
    items = PluginProvider().load()
    assert items[0].disabled is False
    assert items[0].status == "enabled"


def test_skips_entries_without_name(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    cfg = {"installedPlugins": [{"version": "1.0"}, {"name": "", "version": "2.0"}]}
    (tmp_path / "config.json").write_text(json.dumps(cfg))
    assert PluginProvider().load() == []


def test_skips_non_dict_entries(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    cfg = {"installedPlugins": ["just-a-string", 42, None]}
    (tmp_path / "config.json").write_text(json.dumps(cfg))
    assert PluginProvider().load() == []


def test_items_are_frozen():
    info = PluginInfo(name="test")
    try:
        info.name = "changed"  # type: ignore[misc]
        raise AssertionError("Should have raised FrozenInstanceError")
    except AttributeError:
        pass


def test_status_enabled():
    info = PluginInfo(name="p", installed=True, disabled=False)
    assert info.status == "enabled"
    assert info.reason == ""


def test_status_disabled():
    info = PluginInfo(name="p", installed=True, disabled=True)
    assert info.status == "disabled"
    assert info.reason == ""


def test_status_missing():
    info = PluginInfo(name="p", installed=False)
    assert info.status == "missing"
    assert info.reason == "not installed"


def test_install_path_detected(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    plugin_dir = tmp_path / "installed-plugins" / "msx-mcp-v1"
    plugin_dir.mkdir(parents=True)
    cfg = {"installedPlugins": [{"name": "msx-mcp", "cache_path": "msx-mcp-v1", "marketplace": "copilot"}]}
    (tmp_path / "config.json").write_text(json.dumps(cfg))
    items = PluginProvider().load()
    assert items[0].install_path == str(plugin_dir)


def test_bundled_servers_from_mcp_json(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    plugin_dir = tmp_path / "installed-plugins" / "my-plugin"
    plugin_dir.mkdir(parents=True)
    mcp = {"mcpServers": {"server-a": {}, "server-b": {}}}
    (plugin_dir / ".mcp.json").write_text(json.dumps(mcp))
    cfg = {"installedPlugins": [{"name": "my-plugin", "cache_path": "my-plugin", "marketplace": "copilot"}]}
    (tmp_path / "config.json").write_text(json.dumps(cfg))
    items = PluginProvider().load()
    assert set(items[0].bundled_servers) == {"server-a", "server-b"}


def test_bundled_skills_from_skills_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    plugin_dir = tmp_path / "installed-plugins" / "sk-plugin"
    (plugin_dir / "skills" / "skill-one").mkdir(parents=True)
    (plugin_dir / "skills" / "skill-two").mkdir(parents=True)
    cfg = {"installedPlugins": [{"name": "sk-plugin", "cache_path": "sk-plugin", "marketplace": "copilot"}]}
    (tmp_path / "config.json").write_text(json.dumps(cfg))
    items = PluginProvider().load()
    assert set(items[0].bundled_skills) == {"skill-one", "skill-two"}


def test_bundled_agents_from_agents_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    plugin_dir = tmp_path / "installed-plugins" / "ag-plugin"
    agents_dir = plugin_dir / "agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "reviewer.agent.md").write_text("# Reviewer")
    (agents_dir / "helper.agent.md").write_text("# Helper")
    (agents_dir / "notes.txt").write_text("not an agent")
    cfg = {"installedPlugins": [{"name": "ag-plugin", "cache_path": "ag-plugin", "marketplace": "copilot"}]}
    (tmp_path / "config.json").write_text(json.dumps(cfg))
    items = PluginProvider().load()
    assert set(items[0].bundled_agents) == {"reviewer", "helper"}


def test_default_enabled_when_no_enabled_field(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    cfg = {"installedPlugins": [{"name": "default-plugin", "marketplace": "copilot"}]}
    (tmp_path / "config.json").write_text(json.dumps(cfg))
    items = PluginProvider().load()
    assert items[0].disabled is False


def test_null_enabled_plugins_map(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    cfg = {
        "installedPlugins": [{"name": "p", "marketplace": "copilot"}],
        "enabledPlugins": None,
    }
    (tmp_path / "config.json").write_text(json.dumps(cfg))
    items = PluginProvider().load()
    assert items[0].disabled is False


def test_null_installed_plugins_list(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    cfg = {"installedPlugins": None}
    (tmp_path / "config.json").write_text(json.dumps(cfg))
    assert PluginProvider().load() == []


def test_parses_plugins_from_jsonc_config(tmp_path, monkeypatch):
    """Copilot CLI writes // comments at the top of config.json (JSONC)."""
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    content = "// User settings belong in settings.json.\n// This file is managed automatically.\n" + json.dumps(
        {"installedPlugins": [{"name": "test-plugin", "version": "1.0"}]}
    )
    (tmp_path / "config.json").write_text(content)
    items = PluginProvider().load()
    assert len(items) == 1
    assert items[0].name == "test-plugin"


def test_version_from_package_json_preferred(tmp_path, monkeypatch):
    """When package.json exists, its version takes priority over config.json."""
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    plugin_dir = tmp_path / "installed-plugins" / "my-plugin"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "package.json").write_text(json.dumps({"version": "2.0.0"}))
    cfg = {"installedPlugins": [{"name": "my-plugin", "version": "1.0.0", "cache_path": "my-plugin"}]}
    (tmp_path / "config.json").write_text(json.dumps(cfg))
    items = PluginProvider().load()
    assert items[0].version == "2.0.0"


def test_version_falls_back_to_config_without_package_json(tmp_path, monkeypatch):
    """Without package.json, config.json version is used."""
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    plugin_dir = tmp_path / "installed-plugins" / "my-plugin"
    plugin_dir.mkdir(parents=True)
    cfg = {"installedPlugins": [{"name": "my-plugin", "version": "1.5.0", "cache_path": "my-plugin"}]}
    (tmp_path / "config.json").write_text(json.dumps(cfg))
    items = PluginProvider().load()
    assert items[0].version == "1.5.0"


def test_set_plugin_enabled_with_jsonc_config(tmp_path, monkeypatch):
    """set_plugin_enabled must handle JSONC comments in config.json."""
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    content = "// comment\n" + json.dumps(
        {"installedPlugins": [{"name": "p", "marketplace": "copilot", "enabled": True}]}
    )
    (tmp_path / "config.json").write_text(content)
    assert set_plugin_enabled("p", False) is True
    reloaded = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    assert reloaded["installedPlugins"][0]["enabled"] is False
