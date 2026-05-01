"""Copilot CLI path resolution and application constants.

All path helpers are functions (not module-level constants) so that tests can
override ``COPILOT_HOME`` via environment variable.
"""

from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "copilot-setup"
APP_VERSION: str


def _get_version() -> str:
    from importlib.metadata import version

    return version("copilot-setup")


try:
    APP_VERSION = _get_version()
except Exception:
    APP_VERSION = "0.1.0"

# Environment variable prefixes relevant to Copilot CLI configuration.
ENV_PREFIXES = (
    "COPILOT_",
    "OTEL_",
    "GH_",
    "GITHUB_",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "NO_PROXY",
    "NO_COLOR",
    "COLORFGBG",
)

# Patterns in env var names that indicate sensitive values (for masking).
SENSITIVE_PATTERNS = ("TOKEN", "KEY", "SECRET", "PASSWORD", "PASS", "AUTH")


def copilot_home() -> Path:
    """Return the Copilot CLI configuration directory.

    Respects ``COPILOT_HOME`` env var for testing; falls back to ``~/.copilot``.
    """
    return Path(os.environ.get("COPILOT_HOME", str(Path.home() / ".copilot")))


def config_json() -> Path:
    return copilot_home() / "config.json"


def mcp_config_json() -> Path:
    return copilot_home() / "mcp-config.json"


def lsp_config_json() -> Path:
    return copilot_home() / "lsp-config.json"


def installed_plugins_dir() -> Path:
    return copilot_home() / "installed-plugins"


def skills_dir() -> Path:
    return copilot_home() / "skills"


def agents_dir() -> Path:
    return copilot_home() / "agents"


def extensions_dir() -> Path:
    return copilot_home() / "extensions"


def profiles_dir() -> Path:
    return copilot_home() / "profiles"


def mcp_oauth_dir() -> Path:
    return copilot_home() / "mcp-oauth-config"


def upgrade_cache_json() -> Path:
    """Return the path for the upgrade check result cache."""
    return copilot_home() / "upgrade-cache.json"
