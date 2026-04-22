"""Tests for copilotsetup.data.lsp_servers — LSP server config loading."""

from __future__ import annotations

import json
from unittest.mock import patch

from copilotsetup.data.lsp_servers import LspInfo, LspServerProvider


def test_returns_empty_when_file_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    items = LspServerProvider().load()
    assert items == []


def test_returns_empty_when_lsp_servers_key_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    (tmp_path / "lsp-config.json").write_text(json.dumps({"other": "data"}))
    items = LspServerProvider().load()
    assert items == []


def test_returns_empty_when_lsp_servers_not_dict(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    (tmp_path / "lsp-config.json").write_text(json.dumps({"lspServers": "bad"}))
    items = LspServerProvider().load()
    assert items == []


def test_returns_empty_when_file_is_not_dict(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    (tmp_path / "lsp-config.json").write_text(json.dumps([1, 2, 3]))
    items = LspServerProvider().load()
    assert items == []


def test_parses_server_entries(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    config = {
        "lspServers": {
            "typescript": {
                "command": "typescript-language-server",
                "args": ["--stdio"],
            },
            "python": {
                "command": "pylsp",
            },
        }
    }
    (tmp_path / "lsp-config.json").write_text(json.dumps(config))

    with patch("copilotsetup.data.lsp_servers.validate_lsp_binary", return_value=True):
        items = LspServerProvider().load()

    assert len(items) == 2
    # Sorted by name
    assert items[0].name == "python"
    assert items[0].command == "pylsp"
    assert items[0].args == ()
    assert items[0].binary_ok is True

    assert items[1].name == "typescript"
    assert items[1].command == "typescript-language-server"
    assert items[1].args == ("--stdio",)
    assert items[1].binary_ok is True


def test_skips_non_dict_entries(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    config = {
        "lspServers": {
            "good": {"command": "pylsp"},
            "bad": "not-a-dict",
        }
    }
    (tmp_path / "lsp-config.json").write_text(json.dumps(config))

    with patch("copilotsetup.data.lsp_servers.validate_lsp_binary", return_value=True):
        items = LspServerProvider().load()

    assert len(items) == 1
    assert items[0].name == "good"


def test_items_are_frozen():
    info = LspInfo(name="ts", command="tsc")
    try:
        info.name = "other"  # type: ignore[misc]
        raise AssertionError("Should have raised FrozenInstanceError")
    except AttributeError:
        pass


def test_status_enabled_when_binary_ok():
    info = LspInfo(name="ts", command="tsc", binary_ok=True)
    assert info.status == "enabled"
    assert info.reason == ""


def test_status_missing_when_binary_not_ok():
    info = LspInfo(name="ts", command="tsc", binary_ok=False)
    assert info.status == "missing"
    assert info.reason == "binary not found"


def test_validate_lsp_binary_is_called(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    config = {
        "lspServers": {
            "myserver": {"command": "my-lsp", "args": ["--flag"]},
        }
    }
    (tmp_path / "lsp-config.json").write_text(json.dumps(config))

    with patch("copilotsetup.data.lsp_servers.validate_lsp_binary", return_value=False) as mock_validate:
        items = LspServerProvider().load()

    mock_validate.assert_called_once_with("my-lsp", ["--flag"])
    assert len(items) == 1
    assert items[0].binary_ok is False


def test_empty_command_skips_validation(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    config = {
        "lspServers": {
            "nocommand": {"command": ""},
        }
    }
    (tmp_path / "lsp-config.json").write_text(json.dumps(config))

    with patch("copilotsetup.data.lsp_servers.validate_lsp_binary") as mock_validate:
        items = LspServerProvider().load()

    mock_validate.assert_not_called()
    assert len(items) == 1
    assert items[0].binary_ok is False


def test_args_defaults_to_empty_tuple(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    config = {"lspServers": {"srv": {"command": "cmd"}}}
    (tmp_path / "lsp-config.json").write_text(json.dumps(config))

    with patch("copilotsetup.data.lsp_servers.validate_lsp_binary", return_value=True):
        items = LspServerProvider().load()

    assert items[0].args == ()


def test_non_list_args_treated_as_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    config = {"lspServers": {"srv": {"command": "cmd", "args": "bad"}}}
    (tmp_path / "lsp-config.json").write_text(json.dumps(config))

    with patch("copilotsetup.data.lsp_servers.validate_lsp_binary", return_value=True):
        items = LspServerProvider().load()

    assert items[0].args == ()
