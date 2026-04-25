"""Extra tests for copilotsetup.config — edge cases and type guarantees."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from copilotsetup.config import (
    ENV_PREFIXES,
    SENSITIVE_PATTERNS,
    agents_dir,
    config_json,
    copilot_home,
    extensions_dir,
    installed_plugins_dir,
    lsp_config_json,
    mcp_config_json,
    mcp_oauth_dir,
    profiles_dir,
    skills_dir,
)


def test_copilot_home_default(monkeypatch: object) -> None:
    """When COPILOT_HOME is not set, copilot_home() returns ~/.copilot."""
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("COPILOT_HOME", None)
        result = copilot_home()
        assert result == Path.home() / ".copilot"


def test_copilot_home_custom(tmp_path: Path) -> None:
    """When COPILOT_HOME is set, copilot_home() returns that path."""
    with patch.dict(os.environ, {"COPILOT_HOME": str(tmp_path)}):
        assert copilot_home() == tmp_path


def test_all_path_functions_under_home(tmp_path: Path) -> None:
    """Every path helper returns a child of copilot_home()."""
    with patch.dict(os.environ, {"COPILOT_HOME": str(tmp_path)}):
        home = copilot_home()
        path_fns = [
            config_json,
            mcp_config_json,
            lsp_config_json,
            installed_plugins_dir,
            skills_dir,
            agents_dir,
            extensions_dir,
            profiles_dir,
            mcp_oauth_dir,
        ]
        for fn in path_fns:
            result = fn()
            assert str(result).startswith(str(home)), f"{fn.__name__}() = {result} is not under {home}"


def test_env_prefixes_is_tuple() -> None:
    """ENV_PREFIXES is a tuple (immutable sequence)."""
    assert isinstance(ENV_PREFIXES, tuple)
    assert len(ENV_PREFIXES) > 0
    assert all(isinstance(p, str) for p in ENV_PREFIXES)


def test_sensitive_patterns_is_tuple() -> None:
    """SENSITIVE_PATTERNS is a tuple (immutable sequence)."""
    assert isinstance(SENSITIVE_PATTERNS, tuple)
    assert len(SENSITIVE_PATTERNS) > 0
    assert all(isinstance(p, str) for p in SENSITIVE_PATTERNS)


def test_copilot_home_returns_path_object() -> None:
    """copilot_home() always returns a Path, not a string."""
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("COPILOT_HOME", None)
        assert isinstance(copilot_home(), Path)


def test_copilot_home_custom_returns_path_object(tmp_path: Path) -> None:
    """copilot_home() returns a Path even when COPILOT_HOME is set."""
    with patch.dict(os.environ, {"COPILOT_HOME": str(tmp_path)}):
        assert isinstance(copilot_home(), Path)
