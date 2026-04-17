"""Tests for oauth_status — scanning ~/.copilot/mcp-oauth-config/ entries."""

from __future__ import annotations

import json
from pathlib import Path

from copilotsetup.oauth_status import (
    build_status_map,
    scan_oauth_configs,
    status_for,
)


def _write_oauth_entry(
    config_dir: Path,
    digest: str,
    server_url: str,
    with_tokens: bool = True,
) -> None:
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / f"{digest}.json").write_text(
        json.dumps({"serverUrl": server_url, "clientId": "x", "redirectUri": "http://127.0.0.1/"}),
        "utf-8",
    )
    if with_tokens:
        (config_dir / f"{digest}.tokens.json").write_text(
            json.dumps({"access_token": "abc", "refresh_token": "def"}),
            "utf-8",
        )


def test_scan_empty_dir(tmp_path: Path) -> None:
    assert scan_oauth_configs(tmp_path / "missing") == []
    empty = tmp_path / "empty"
    empty.mkdir()
    assert scan_oauth_configs(empty) == []


def test_scan_with_tokens(tmp_path: Path) -> None:
    _write_oauth_entry(tmp_path, "abc123", "https://example.com/mcp", with_tokens=True)
    entries = scan_oauth_configs(tmp_path)
    assert len(entries) == 1
    assert entries[0].server_url == "https://example.com/mcp"
    assert entries[0].has_tokens is True


def test_scan_without_tokens(tmp_path: Path) -> None:
    _write_oauth_entry(tmp_path, "abc", "https://example.com/mcp", with_tokens=False)
    entries = scan_oauth_configs(tmp_path)
    assert len(entries) == 1
    assert entries[0].has_tokens is False


def test_scan_skips_malformed(tmp_path: Path) -> None:
    tmp_path.mkdir(exist_ok=True)
    (tmp_path / "bad.json").write_text("{not json", "utf-8")
    _write_oauth_entry(tmp_path, "good", "https://ok.example/mcp", with_tokens=True)
    entries = scan_oauth_configs(tmp_path)
    assert len(entries) == 1
    assert entries[0].server_url == "https://ok.example/mcp"


def test_status_map_authenticated(tmp_path: Path) -> None:
    _write_oauth_entry(tmp_path, "a", "https://a.example/mcp", with_tokens=True)
    _write_oauth_entry(tmp_path, "b", "https://b.example/mcp", with_tokens=False)
    smap = build_status_map(scan_oauth_configs(tmp_path))
    assert smap["https://a.example/mcp"] == "authenticated"
    assert smap["https://b.example/mcp"] == "needs_auth"


def test_status_for_trailing_slash_tolerance() -> None:
    smap = {"https://example.com/mcp": "authenticated"}
    assert status_for("https://example.com/mcp", smap) == "authenticated"
    assert status_for("https://example.com/mcp/", smap) == "authenticated"


def test_status_for_unknown_url_defaults_to_not_applicable() -> None:
    smap: dict[str, str] = {}
    assert status_for("https://unknown.example/mcp", smap) == "not_applicable"
