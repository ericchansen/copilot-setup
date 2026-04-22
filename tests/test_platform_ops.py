"""Tests for copilotsetup.platform_ops — link detection and LSP binary helpers."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from copilotsetup.platform_ops import (
    _build_lsp_command,
    get_link_target,
    is_link,
    validate_lsp_binary,
)

# ---------------------------------------------------------------------------
# is_link
# ---------------------------------------------------------------------------


def test_is_link_regular_dir(tmp_path: Path) -> None:
    regular = tmp_path / "plain"
    regular.mkdir()
    assert is_link(regular) is False


def test_is_link_symlink(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation requires elevated privileges on this OS")
    assert is_link(link) is True


def test_is_link_nonexistent(tmp_path: Path) -> None:
    assert is_link(tmp_path / "does-not-exist") is False


# ---------------------------------------------------------------------------
# get_link_target
# ---------------------------------------------------------------------------


def test_get_link_target_not_a_link(tmp_path: Path) -> None:
    regular = tmp_path / "plain"
    regular.mkdir()
    assert get_link_target(regular) is None


def test_get_link_target_symlink(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation requires elevated privileges on this OS")
    result = get_link_target(link)
    assert result is not None
    # On Windows, readlink() may return \\?\ prefixed paths — normalize both sides.
    result_str = str(result).removeprefix("\\\\?\\")
    target_str = str(target.resolve()).removeprefix("\\\\?\\")
    assert result_str == target_str


# ---------------------------------------------------------------------------
# validate_lsp_binary
# ---------------------------------------------------------------------------


def test_validate_lsp_binary_not_found() -> None:
    with patch("copilotsetup.platform_ops.shutil.which", return_value=None):
        assert validate_lsp_binary("nonexistent-lsp", ["--stdio"]) is False


def test_validate_lsp_binary_timeout() -> None:
    mock_proc = MagicMock()
    # First wait(timeout=2) raises TimeoutExpired; second wait() after kill() succeeds.
    mock_proc.wait.side_effect = [subprocess.TimeoutExpired(cmd="lsp", timeout=2), None]
    mock_proc.kill.return_value = None

    with (
        patch("copilotsetup.platform_ops.shutil.which", return_value="/usr/bin/lsp"),
        patch("copilotsetup.platform_ops.subprocess.Popen", return_value=mock_proc),
        patch("copilotsetup.platform_ops._build_lsp_command", return_value=["/usr/bin/lsp", "--stdio"]),
    ):
        assert validate_lsp_binary("lsp", ["--stdio"]) is True
    mock_proc.kill.assert_called_once()


def test_validate_lsp_binary_exits_zero() -> None:
    mock_proc = MagicMock()
    mock_proc.wait.return_value = None
    mock_proc.returncode = 0

    with (
        patch("copilotsetup.platform_ops.shutil.which", return_value="/usr/bin/lsp"),
        patch("copilotsetup.platform_ops.subprocess.Popen", return_value=mock_proc),
        patch("copilotsetup.platform_ops._build_lsp_command", return_value=["/usr/bin/lsp", "--stdio"]),
    ):
        assert validate_lsp_binary("lsp", ["--stdio"]) is True


def test_validate_lsp_binary_exits_nonzero() -> None:
    mock_proc = MagicMock()
    mock_proc.wait.return_value = None
    mock_proc.returncode = 1

    with (
        patch("copilotsetup.platform_ops.shutil.which", return_value="/usr/bin/lsp"),
        patch("copilotsetup.platform_ops.subprocess.Popen", return_value=mock_proc),
        patch("copilotsetup.platform_ops._build_lsp_command", return_value=["/usr/bin/lsp", "--stdio"]),
    ):
        assert validate_lsp_binary("lsp", ["--stdio"]) is False


# ---------------------------------------------------------------------------
# _build_lsp_command
# ---------------------------------------------------------------------------


def test_build_lsp_command_unix() -> None:
    with patch("copilotsetup.platform_ops.IS_WINDOWS", False):
        result = _build_lsp_command("/usr/bin/typescript-language-server", ["--stdio"])
    assert result == ["/usr/bin/typescript-language-server", "--stdio"]


def test_build_lsp_command_ps1_with_cmd_sibling(tmp_path: Path) -> None:
    ps1_file = tmp_path / "server.ps1"
    cmd_file = tmp_path / "server.cmd"
    ps1_file.write_text("# ps1 stub")
    cmd_file.write_text(":: cmd stub")

    with patch("copilotsetup.platform_ops.IS_WINDOWS", True):
        result = _build_lsp_command(str(ps1_file), ["--stdio"])
    assert result == ["cmd", "/c", f"{cmd_file} --stdio"]


def test_build_lsp_command_cmd(tmp_path: Path) -> None:
    cmd_file = tmp_path / "server.cmd"
    cmd_file.write_text(":: cmd stub")

    with patch("copilotsetup.platform_ops.IS_WINDOWS", True):
        result = _build_lsp_command(str(cmd_file), ["--stdio"])
    assert result == ["cmd", "/c", f"{cmd_file} --stdio"]


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only .ps1 fallback path")
def test_build_lsp_command_ps1_no_cmd_sibling(tmp_path: Path) -> None:
    ps1_file = tmp_path / "server.ps1"
    ps1_file.write_text("# ps1 stub")

    with patch("copilotsetup.platform_ops.IS_WINDOWS", True):
        result = _build_lsp_command(str(ps1_file), ["--stdio"])
    assert result == ["pwsh", "-NoProfile", "-File", str(ps1_file), "--stdio"]


def test_build_lsp_command_no_args() -> None:
    with patch("copilotsetup.platform_ops.IS_WINDOWS", False):
        result = _build_lsp_command("/usr/bin/lsp", [])
    assert result == ["/usr/bin/lsp"]
