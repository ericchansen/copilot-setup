"""Tests for copilotsetup.config — path resolution and constants."""

from __future__ import annotations

import os
from unittest.mock import patch

from copilotsetup.config import (
    APP_NAME,
    APP_VERSION,
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


def test_copilot_home_default():
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("COPILOT_HOME", None)
        home = copilot_home()
        assert home.name == ".copilot"


def test_copilot_home_env_override(tmp_path):
    with patch.dict(os.environ, {"COPILOT_HOME": str(tmp_path)}):
        assert copilot_home() == tmp_path


def test_child_paths_follow_home(tmp_path):
    with patch.dict(os.environ, {"COPILOT_HOME": str(tmp_path)}):
        assert config_json() == tmp_path / "config.json"
        assert mcp_config_json() == tmp_path / "mcp-config.json"
        assert lsp_config_json() == tmp_path / "lsp-config.json"
        assert installed_plugins_dir() == tmp_path / "installed-plugins"
        assert skills_dir() == tmp_path / "skills"
        assert agents_dir() == tmp_path / "agents"
        assert extensions_dir() == tmp_path / "extensions"
        assert profiles_dir() == tmp_path / "profiles"
        assert mcp_oauth_dir() == tmp_path / "mcp-oauth-config"


def test_constants():
    assert APP_NAME == "copilot-setup"
    assert isinstance(APP_VERSION, str)
    assert len(ENV_PREFIXES) > 0
    assert len(SENSITIVE_PATTERNS) > 0
