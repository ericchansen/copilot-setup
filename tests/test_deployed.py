"""Tests for the vanilla ``~/.copilot/`` readers in ``deployed.py``."""

from __future__ import annotations

import json
from unittest.mock import patch

from copilotsetup import deployed


def _stub_home(tmp_path, monkeypatch):
    """Redirect deployed._copilot_home() to a tmp_path so we don't touch the real HOME."""
    fake_home = tmp_path / ".copilot"
    fake_home.mkdir()
    monkeypatch.setattr(deployed, "_copilot_home", lambda: fake_home)
    return fake_home


class TestReadMcpConfig:
    def test_missing_file_returns_empty(self, tmp_path, monkeypatch):
        _stub_home(tmp_path, monkeypatch)
        assert deployed.read_mcp_config() == {}

    def test_malformed_json_returns_empty(self, tmp_path, monkeypatch):
        home = _stub_home(tmp_path, monkeypatch)
        (home / "mcp-config.json").write_text("not json", encoding="utf-8")
        assert deployed.read_mcp_config() == {}

    def test_missing_mcpServers_key_returns_empty(self, tmp_path, monkeypatch):
        home = _stub_home(tmp_path, monkeypatch)
        (home / "mcp-config.json").write_text(json.dumps({"other": 1}), encoding="utf-8")
        assert deployed.read_mcp_config() == {}

    def test_parses_servers_preserving_source_stamp(self, tmp_path, monkeypatch):
        home = _stub_home(tmp_path, monkeypatch)
        data = {
            "mcpServers": {
                "github": {
                    "type": "http",
                    "url": "https://api.githubcopilot.com/mcp/",
                    "source": "user",
                    "sourcePath": "~/.copilot/mcp-config.json",
                },
                "context7": {
                    "type": "http",
                    "url": "https://mcp.context7.com/mcp",
                    "source": "user",
                },
            }
        }
        (home / "mcp-config.json").write_text(json.dumps(data), encoding="utf-8")
        result = deployed.read_mcp_config()
        assert set(result) == {"github", "context7"}
        assert result["github"]["source"] == "user"
        assert result["github"]["url"] == "https://api.githubcopilot.com/mcp/"

    def test_skips_non_dict_values(self, tmp_path, monkeypatch):
        home = _stub_home(tmp_path, monkeypatch)
        data = {"mcpServers": {"good": {"url": "x"}, "bad": "not a dict"}}
        (home / "mcp-config.json").write_text(json.dumps(data), encoding="utf-8")
        assert set(deployed.read_mcp_config()) == {"good"}


class TestReadLspConfig:
    def test_missing_file_returns_empty(self, tmp_path, monkeypatch):
        _stub_home(tmp_path, monkeypatch)
        assert deployed.read_lsp_config() == {}

    def test_returns_lspServers_wrapper(self, tmp_path, monkeypatch):
        home = _stub_home(tmp_path, monkeypatch)
        data = {
            "lspServers": {
                "typescript": {"command": "tsserver", "args": [], "fileExtensions": [".ts"]},
                "python": {"command": "pyright", "args": [], "fileExtensions": [".py"]},
            }
        }
        (home / "lsp-config.json").write_text(json.dumps(data), encoding="utf-8")
        result = deployed.read_lsp_config()
        assert "lspServers" in result
        assert set(result["lspServers"]) == {"typescript", "python"}

    def test_malformed_returns_empty(self, tmp_path, monkeypatch):
        home = _stub_home(tmp_path, monkeypatch)
        (home / "lsp-config.json").write_text("{{", encoding="utf-8")
        assert deployed.read_lsp_config() == {}


class TestReadInstalledPlugins:
    def test_missing_file_returns_empty(self, tmp_path, monkeypatch):
        _stub_home(tmp_path, monkeypatch)
        assert deployed.read_installed_plugins() == {}

    def test_parses_marketplace_plugin(self, tmp_path, monkeypatch):
        home = _stub_home(tmp_path, monkeypatch)
        data = {
            "installedPlugins": [
                {
                    "name": "peon-ping",
                    "marketplace": "peon-ping-marketplace",
                    "version": "1.2.3",
                    "enabled": True,
                    "cache_path": str(tmp_path / "cache" / "peon-ping"),
                }
            ],
            "enabledPlugins": {"peon-ping@peon-ping-marketplace": True},
        }
        (home / "config.json").write_text(json.dumps(data), encoding="utf-8")
        result = deployed.read_installed_plugins()
        assert "peon-ping" in result
        assert result["peon-ping"]["version"] == "1.2.3"
        assert result["peon-ping"]["disabled"] is False
        assert result["peon-ping"]["source"] == "peon-ping-marketplace"

    def test_enabledPlugins_bare_name_for_direct_install(self, tmp_path, monkeypatch):
        home = _stub_home(tmp_path, monkeypatch)
        data = {
            "installedPlugins": [{"name": "msx-mcp", "marketplace": "", "version": "0.1.0", "enabled": True}],
            "enabledPlugins": {"msx-mcp": False},
        }
        (home / "config.json").write_text(json.dumps(data), encoding="utf-8")
        result = deployed.read_installed_plugins()
        # enabledPlugins takes precedence when present.
        assert result["msx-mcp"]["disabled"] is True
        assert result["msx-mcp"]["source"] == "local"

    def test_skips_malformed_entries(self, tmp_path, monkeypatch):
        home = _stub_home(tmp_path, monkeypatch)
        data = {
            "installedPlugins": [
                "not a dict",
                {"marketplace": "x"},  # no name
                {"name": "good", "version": "1.0"},
            ]
        }
        (home / "config.json").write_text(json.dumps(data), encoding="utf-8")
        result = deployed.read_installed_plugins()
        assert set(result) == {"good"}


class TestScanSkillLinks:
    def test_missing_dir_returns_empty(self, tmp_path, monkeypatch):
        _stub_home(tmp_path, monkeypatch)
        assert deployed.scan_skill_links() == {}

    def test_real_directories_have_empty_target(self, tmp_path, monkeypatch):
        home = _stub_home(tmp_path, monkeypatch)
        skills = home / "skills"
        skills.mkdir()
        (skills / "my-skill").mkdir()
        # Force is_link to return False so this test doesn't depend on junction support.
        with patch.object(deployed, "is_link", return_value=False):
            result = deployed.scan_skill_links()
        assert result == {"my-skill": ""}

    def test_links_record_target(self, tmp_path, monkeypatch):
        home = _stub_home(tmp_path, monkeypatch)
        skills = home / "skills"
        skills.mkdir()
        target = tmp_path / "source-repo" / "skill-a"
        target.mkdir(parents=True)
        (skills / "skill-a").mkdir()  # placeholder — we stub link detection
        with (
            patch.object(deployed, "is_link", return_value=True),
            patch.object(deployed, "get_link_target", return_value=target),
        ):
            result = deployed.scan_skill_links()
        assert result == {"skill-a": str(target)}
