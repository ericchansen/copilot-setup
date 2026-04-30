"""Tests for copilotsetup.utils.cli — run_copilot subprocess wrapper."""

from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest

from copilotsetup.utils.cli import run_copilot


def test_run_copilot_calls_subprocess() -> None:
    """run_copilot passes the correct command list to subprocess.run."""
    fake_result = subprocess.CompletedProcess(
        args=["copilot", "version"],
        returncode=0,
        stdout="1.0.0\n",
        stderr="",
    )
    with patch("copilotsetup.utils.cli.subprocess.run", return_value=fake_result) as mock_run:
        result = run_copilot("version")

    mock_run.assert_called_once_with(
        ["copilot", "version"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30.0,
    )
    assert result.returncode == 0
    assert result.stdout == "1.0.0\n"


def test_run_copilot_multiple_args() -> None:
    """run_copilot spreads multiple arguments correctly."""
    fake_result = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
    with patch("copilotsetup.utils.cli.subprocess.run", return_value=fake_result) as mock_run:
        run_copilot("mcp", "list", "--json")

    mock_run.assert_called_once_with(
        ["copilot", "mcp", "list", "--json"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30.0,
    )


def test_run_copilot_not_found() -> None:
    """run_copilot raises FileNotFoundError when the copilot binary is missing."""
    with (
        patch("copilotsetup.utils.cli.subprocess.run", side_effect=FileNotFoundError("copilot not found")),
        pytest.raises(FileNotFoundError),
    ):
        run_copilot("version")


def test_run_copilot_custom_timeout() -> None:
    """run_copilot forwards custom timeout to subprocess.run."""
    fake_result = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
    with patch("copilotsetup.utils.cli.subprocess.run", return_value=fake_result) as mock_run:
        run_copilot("version", timeout=60.0)

    mock_run.assert_called_once_with(
        ["copilot", "version"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60.0,
    )
