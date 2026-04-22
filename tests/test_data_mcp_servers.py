"""Tests for copilotsetup.data.mcp_servers — MCP server provider."""

from __future__ import annotations

import json

from copilotsetup.data.mcp_servers import McpServerInfo, McpServerProvider


def _write_config(tmp_path, data):
    """Write mcp-config.json to tmp_path and return the path."""
    cfg = tmp_path / "mcp-config.json"
    cfg.write_text(json.dumps(data), encoding="utf-8")
    return cfg


def test_empty_when_file_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    items = McpServerProvider().load()
    assert items == []


def test_empty_when_mcp_servers_key_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    _write_config(tmp_path, {"other": "stuff"})
    items = McpServerProvider().load()
    assert items == []


def test_parses_local_server(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    _write_config(
        tmp_path,
        {
            "mcpServers": {
                "my-tool": {
                    "type": "local",
                    "command": "node",
                    "args": ["server.js", "--port", "3000"],
                }
            }
        },
    )
    items = McpServerProvider().load()
    assert len(items) == 1
    srv = items[0]
    assert srv.name == "my-tool"
    assert srv.server_type == "local"
    assert srv.command == "node"
    assert srv.args == ("server.js", "--port", "3000")
    assert srv.url == ""
    assert srv.env_ok is True
    assert srv.status == "enabled"


def test_parses_http_server(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    _write_config(
        tmp_path,
        {
            "mcpServers": {
                "remote-api": {
                    "type": "http",
                    "url": "https://example.com/mcp",
                    "headers": {"Authorization": "Bearer abc"},
                }
            }
        },
    )
    items = McpServerProvider().load()
    assert len(items) == 1
    srv = items[0]
    assert srv.name == "remote-api"
    assert srv.server_type == "http"
    assert srv.url == "https://example.com/mcp"
    assert srv.command == ""
    assert srv.env_ok is True


def test_detects_missing_env_vars(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    monkeypatch.delenv("MY_SECRET", raising=False)
    _write_config(
        tmp_path,
        {
            "mcpServers": {
                "needs-env": {
                    "type": "local",
                    "command": "python",
                    "env": {
                        "API_KEY": "${MY_SECRET}",
                        "STATIC": "literal-value",
                    },
                }
            }
        },
    )
    items = McpServerProvider().load()
    assert len(items) == 1
    srv = items[0]
    assert srv.env_ok is False
    assert "MY_SECRET" in srv.missing_env
    assert srv.status == "broken"
    assert "MY_SECRET" in srv.reason


def test_env_ok_when_vars_present(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    monkeypatch.setenv("MY_SECRET", "s3cret")
    _write_config(
        tmp_path,
        {
            "mcpServers": {
                "has-env": {
                    "type": "local",
                    "command": "python",
                    "env": {"API_KEY": "${MY_SECRET}"},
                }
            }
        },
    )
    items = McpServerProvider().load()
    assert len(items) == 1
    assert items[0].env_ok is True
    assert items[0].status == "enabled"


def test_items_are_frozen():
    info = McpServerInfo(name="test")
    try:
        info.name = "changed"  # type: ignore[misc]
        assert False, "Should have raised FrozenInstanceError"
    except AttributeError:
        pass


def test_status_property_enabled():
    info = McpServerInfo(name="ok", env_ok=True)
    assert info.status == "enabled"
    assert info.reason == ""


def test_status_property_broken():
    info = McpServerInfo(name="bad", env_ok=False, missing_env=("FOO", "BAR"))
    assert info.status == "broken"
    assert "FOO" in info.reason
    assert "BAR" in info.reason


def test_status_broken_no_missing_env():
    info = McpServerInfo(name="bad", env_ok=False)
    assert info.status == "broken"
    assert info.reason == "env missing"


def test_sorted_by_name(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    _write_config(
        tmp_path,
        {
            "mcpServers": {
                "zebra": {"type": "local", "command": "z"},
                "alpha": {"type": "local", "command": "a"},
                "middle": {"type": "http", "url": "http://m"},
            }
        },
    )
    items = McpServerProvider().load()
    names = [s.name for s in items]
    assert names == ["alpha", "middle", "zebra"]


def test_skips_non_dict_entries(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    _write_config(
        tmp_path,
        {
            "mcpServers": {
                "good": {"type": "local", "command": "node"},
                "bad": "not-a-dict",
                "also-bad": 42,
            }
        },
    )
    items = McpServerProvider().load()
    assert len(items) == 1
    assert items[0].name == "good"


def test_default_type_is_local(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    _write_config(
        tmp_path,
        {"mcpServers": {"no-type": {"command": "node"}}},
    )
    items = McpServerProvider().load()
    assert len(items) == 1
    assert items[0].server_type == "local"


def test_env_with_dollar_no_braces(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    monkeypatch.delenv("BARE_VAR", raising=False)
    _write_config(
        tmp_path,
        {
            "mcpServers": {
                "bare": {
                    "command": "x",
                    "env": {"KEY": "$BARE_VAR"},
                }
            }
        },
    )
    items = McpServerProvider().load()
    assert items[0].env_ok is False
    assert "BARE_VAR" in items[0].missing_env


def test_source_from_plugin(tmp_path, monkeypatch):
    """Servers in mcp-config.json that match a plugin .mcp.json get the plugin as source."""
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    # Create mcp-config.json with a server
    _write_config(tmp_path, {"mcpServers": {"my-srv": {"command": "node"}}})
    # Create config.json with a plugin
    cfg = tmp_path / "config.json"
    plugin_dir = tmp_path / "installed-plugins" / "my-plugin"
    plugin_dir.mkdir(parents=True)
    cfg.write_text(
        json.dumps({"installedPlugins": [{"name": "my-plugin", "cache_path": "my-plugin"}]}),
        encoding="utf-8",
    )
    # Create .mcp.json in the plugin declaring the same server
    mcp_json = plugin_dir / ".mcp.json"
    mcp_json.write_text(
        json.dumps({"mcpServers": {"my-srv": {"command": "node"}}}),
        encoding="utf-8",
    )
    items = McpServerProvider().load()
    assert len(items) == 1
    assert items[0].source == "my-plugin"


def test_plugin_only_servers_appear(tmp_path, monkeypatch):
    """Servers only in a plugin .mcp.json (not in mcp-config.json) still show up."""
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    # Empty mcp-config.json
    _write_config(tmp_path, {"mcpServers": {}})
    # Plugin with a server
    plugin_dir = tmp_path / "installed-plugins" / "test-plugin"
    plugin_dir.mkdir(parents=True)
    cfg = tmp_path / "config.json"
    cfg.write_text(
        json.dumps({"installedPlugins": [{"name": "test-plugin", "cache_path": "test-plugin"}]}),
        encoding="utf-8",
    )
    mcp_json = plugin_dir / ".mcp.json"
    mcp_json.write_text(
        json.dumps({"mcpServers": {"plugin-srv": {"type": "http", "url": "https://example.com"}}}),
        encoding="utf-8",
    )
    items = McpServerProvider().load()
    assert len(items) == 1
    assert items[0].name == "plugin-srv"
    assert items[0].source == "test-plugin"
    assert items[0].server_type == "http"


def test_source_defaults_to_config(tmp_path, monkeypatch):
    """Servers not matching any plugin get source='config'."""
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    _write_config(tmp_path, {"mcpServers": {"standalone": {"command": "node"}}})
    items = McpServerProvider().load()
    assert len(items) == 1
    assert items[0].source == "config"
