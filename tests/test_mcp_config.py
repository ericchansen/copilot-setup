"""Tests for MCP config generation — user server preservation and env fields."""

from __future__ import annotations

import json
from pathlib import Path

from copilotsetup.config import generate_mcp_config


def _write_mcp_config(path: Path, servers: dict) -> None:
    """Write an mcp-config.json to *path*."""
    path.write_text(json.dumps({"mcpServers": servers}, indent=2) + "\n", "utf-8")


def _read_mcp_config(path: Path) -> dict:
    """Read mcpServers from *path*."""
    return json.loads(path.read_text("utf-8")).get("mcpServers", {})


class TestUserServerPreservation:
    """User-added servers should survive generate_mcp_config runs."""

    def test_user_server_preserved(self, tmp_path: Path) -> None:
        output = tmp_path / "mcp-config.json"
        _write_mcp_config(
            output,
            {
                "user-zotero": {"type": "local", "command": "zotero-mcp", "args": [], "tools": ["*"]},
            },
        )

        managed = {"azure-mcp": {"command": "npx", "args": ["-y", "@azure/mcp@latest"]}}
        info = generate_mcp_config(managed, {}, tmp_path, output)

        result = _read_mcp_config(output)
        assert "azure-mcp" in result
        assert "user-zotero" in result
        assert info["preserved"] == ["user-zotero"]

    def test_multiple_user_servers_preserved(self, tmp_path: Path) -> None:
        output = tmp_path / "mcp-config.json"
        _write_mcp_config(
            output,
            {
                "zotero": {"type": "local", "command": "zotero-mcp", "args": [], "tools": ["*"]},
                "custom-db": {"type": "local", "command": "db-mcp", "args": [], "tools": ["*"]},
            },
        )

        managed = {"azure-mcp": {"command": "npx", "args": ["-y", "@azure/mcp@latest"]}}
        info = generate_mcp_config(managed, {}, tmp_path, output)

        result = _read_mcp_config(output)
        assert "azure-mcp" in result
        assert "zotero" in result
        assert "custom-db" in result
        assert sorted(info["preserved"]) == ["custom-db", "zotero"]

    def test_managed_overrides_same_name(self, tmp_path: Path) -> None:
        output = tmp_path / "mcp-config.json"
        _write_mcp_config(
            output,
            {
                "azure-mcp": {"type": "local", "command": "old-command", "args": [], "tools": ["*"]},
            },
        )

        managed = {"azure-mcp": {"command": "npx", "args": ["-y", "@azure/mcp@latest"]}}
        info = generate_mcp_config(managed, {}, tmp_path, output)

        result = _read_mcp_config(output)
        assert result["azure-mcp"]["command"] == "npx"
        assert "azure-mcp" in info["overridden"]
        assert info["preserved"] == []

    def test_no_existing_config(self, tmp_path: Path) -> None:
        output = tmp_path / "mcp-config.json"
        # File doesn't exist yet

        managed = {"azure-mcp": {"command": "npx", "args": ["-y", "@azure/mcp@latest"]}}
        info = generate_mcp_config(managed, {}, tmp_path, output)

        result = _read_mcp_config(output)
        assert "azure-mcp" in result
        assert info["preserved"] == []
        assert info["overridden"] == []

    def test_invalid_existing_json(self, tmp_path: Path) -> None:
        output = tmp_path / "mcp-config.json"
        output.write_text("not valid json!!!", "utf-8")

        managed = {"azure-mcp": {"command": "npx", "args": ["-y", "@azure/mcp@latest"]}}
        info = generate_mcp_config(managed, {}, tmp_path, output)

        result = _read_mcp_config(output)
        assert "azure-mcp" in result
        assert info["preserved"] == []

    def test_malformed_mcp_servers_key(self, tmp_path: Path) -> None:
        output = tmp_path / "mcp-config.json"
        output.write_text(json.dumps({"mcpServers": "not-a-dict"}), "utf-8")

        managed = {"azure-mcp": {"command": "npx", "args": ["-y", "@azure/mcp@latest"]}}
        info = generate_mcp_config(managed, {}, tmp_path, output)

        result = _read_mcp_config(output)
        assert "azure-mcp" in result
        assert info["preserved"] == []


class TestEnvPreservation:
    """The env field should be preserved in generated entries."""

    def test_env_preserved_local_server(self, tmp_path: Path) -> None:
        output = tmp_path / "mcp-config.json"
        managed = {
            "zotero": {
                "command": "zotero-mcp",
                "env": {"ZOTERO_API_KEY": "${ZOTERO_API_KEY}", "ZOTERO_LIBRARY_ID": "1276304"},
            },
        }
        generate_mcp_config(managed, {}, tmp_path, output)

        result = _read_mcp_config(output)
        assert result["zotero"]["env"] == {
            "ZOTERO_API_KEY": "${ZOTERO_API_KEY}",
            "ZOTERO_LIBRARY_ID": "1276304",
        }

    def test_env_preserved_http_server(self, tmp_path: Path) -> None:
        output = tmp_path / "mcp-config.json"
        managed = {
            "my-http": {
                "url": "https://example.com/mcp",
                "env": {"API_TOKEN": "${MY_TOKEN}"},
            },
        }
        generate_mcp_config(managed, {}, tmp_path, output)

        result = _read_mcp_config(output)
        assert result["my-http"]["env"] == {"API_TOKEN": "${MY_TOKEN}"}

    def test_no_env_when_absent(self, tmp_path: Path) -> None:
        output = tmp_path / "mcp-config.json"
        managed = {"simple": {"command": "some-mcp"}}
        generate_mcp_config(managed, {}, tmp_path, output)

        result = _read_mcp_config(output)
        assert "env" not in result["simple"]


class TestTopLevelPreservation:
    """Other top-level keys in the existing config should be preserved."""

    def test_extra_top_level_keys_preserved(self, tmp_path: Path) -> None:
        output = tmp_path / "mcp-config.json"
        output.write_text(
            json.dumps(
                {
                    "mcpServers": {},
                    "someCustomKey": {"setting": True},
                }
            ),
            "utf-8",
        )

        managed = {"azure-mcp": {"command": "npx", "args": ["-y", "@azure/mcp@latest"]}}
        generate_mcp_config(managed, {}, tmp_path, output)

        data = json.loads(output.read_text("utf-8"))
        assert data["someCustomKey"] == {"setting": True}
        assert "azure-mcp" in data["mcpServers"]


class TestUserServerWithEnv:
    """User-added servers with env fields should be fully preserved."""

    def test_user_server_env_survives(self, tmp_path: Path) -> None:
        output = tmp_path / "mcp-config.json"
        _write_mcp_config(
            output,
            {
                "zotero": {
                    "type": "local",
                    "command": "zotero-mcp",
                    "args": [],
                    "tools": ["*"],
                    "env": {"ZOTERO_API_KEY": "secret", "ZOTERO_LIBRARY_ID": "1276304"},
                },
            },
        )

        managed = {"azure-mcp": {"command": "npx", "args": ["-y", "@azure/mcp@latest"]}}
        generate_mcp_config(managed, {}, tmp_path, output)

        result = _read_mcp_config(output)
        assert result["zotero"]["env"] == {
            "ZOTERO_API_KEY": "secret",
            "ZOTERO_LIBRARY_ID": "1276304",
        }
