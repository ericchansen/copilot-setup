"""Tests for copilotsetup.doctor."""

from __future__ import annotations

from unittest.mock import patch

from copilotsetup.doctor import (
    HealthInfo,
    _build_env,
    _fmt_row,
    probe_all,
    probe_server_entry,
    run_cli,
)


def test_build_env_no_overrides():
    """Returns os.environ copy with no missing vars."""
    env, missing = _build_env(None)
    assert isinstance(env, dict)
    assert missing == []


def test_build_env_resolves_env_var(monkeypatch):
    """${VAR} resolves to real env var value."""
    monkeypatch.setenv("DOCTOR_TEST_VAR", "hello123")
    env, missing = _build_env({"MY_KEY": "${DOCTOR_TEST_VAR}"})
    assert env["MY_KEY"] == "hello123"
    assert missing == []


def test_build_env_missing_var():
    """${NONEXISTENT} is reported as missing."""
    env, missing = _build_env({"X": "${NONEXISTENT_VAR_DOCTOR_TEST}"})
    assert "NONEXISTENT_VAR_DOCTOR_TEST" in missing
    assert "X" not in env


def test_probe_server_entry_routes_http():
    """Entry with type=http calls probe_http."""
    entry = {"type": "http", "url": "https://example.com/mcp"}
    with patch("copilotsetup.doctor.probe_http") as mock_http:
        mock_http.return_value = HealthInfo(name="test", server_type="http", health="ok")
        result = probe_server_entry("test", entry)
        mock_http.assert_called_once()
        assert result.health == "ok"


def test_probe_server_entry_routes_stdio():
    """Entry without type calls probe_stdio."""
    entry = {"command": "node", "args": ["server.js"]}
    with patch("copilotsetup.doctor.probe_stdio") as mock_stdio:
        mock_stdio.return_value = HealthInfo(name="test", server_type="local", health="ok")
        result = probe_server_entry("test", entry)
        mock_stdio.assert_called_once()
        assert result.health == "ok"


def test_health_info_defaults():
    """HealthInfo has correct defaults."""
    info = HealthInfo(name="srv", server_type="local", health="ok")
    assert info.detail == ""
    assert info.latency_ms == 0
    assert info.missing_env == []


def test_fmt_row_ok():
    """Formats ok result with checkmark."""
    info = HealthInfo(name="my-server", server_type="local", health="ok", latency_ms=42)
    row = _fmt_row(info)
    assert "✓" in row
    assert "my-server" in row
    assert "42ms" in row


def test_fmt_row_error():
    """Formats spawn_error result with cross mark."""
    info = HealthInfo(
        name="bad-server",
        server_type="local",
        health="spawn_error",
        detail="not found",
    )
    row = _fmt_row(info)
    assert "✗" in row
    assert "bad-server" in row
    assert "spawn_error" in row
    assert "not found" in row


def test_run_cli_no_servers():
    """Returns 0 when no servers configured."""
    with patch("copilotsetup.doctor.read_json", return_value=None):
        assert run_cli() == 0


def test_probe_all_empty():
    """Returns empty list for empty dict."""
    result = probe_all({})
    assert result == []
