"""Tests for copilotsetup.plugin_upgrades — upgrade detection logic."""

from __future__ import annotations

from unittest.mock import patch

from copilotsetup.plugin_upgrades import (
    STATUS_NO_PATH,
    STATUS_NO_UPSTREAM,
    STATUS_NOT_GIT,
    STATUS_UP_TO_DATE,
    STATUS_UPGRADABLE,
    PluginUpgradeInfo,
    _highest_semver_tag,
    _parse_semver,
    check_all,
    check_plugin,
)

# --- _parse_semver ---


def test_parse_semver_plain():
    assert _parse_semver("1.2.3") == (1, 2, 3)


def test_parse_semver_with_v():
    assert _parse_semver("v0.12.1") == (0, 12, 1)


def test_parse_semver_invalid():
    assert _parse_semver("not-a-version") is None
    assert _parse_semver("1.2") is None
    assert _parse_semver("") is None


# --- _highest_semver_tag ---


def test_highest_semver_tag_basic():
    assert _highest_semver_tag(["v1.0.0", "v2.0.0", "v1.5.0"]) == "v2.0.0"


def test_highest_semver_tag_mixed():
    assert _highest_semver_tag(["v1.0.0", "latest", "v0.9.0"]) == "v1.0.0"


def test_highest_semver_tag_empty():
    assert _highest_semver_tag([]) is None


def test_highest_semver_tag_no_valid():
    assert _highest_semver_tag(["alpha", "beta"]) is None


# --- PluginUpgradeInfo properties ---


def test_upgrade_available_true():
    info = PluginUpgradeInfo(name="p", path=None, status=STATUS_UPGRADABLE, latest_version="v2.0.0")
    assert info.upgrade_available is True
    assert info.summary == "↑ v2.0.0"


def test_upgrade_available_false():
    info = PluginUpgradeInfo(name="p", path=None, status=STATUS_UP_TO_DATE)
    assert info.upgrade_available is False
    assert info.summary == ""


# --- check_plugin: path validation ---


def test_check_plugin_no_path():
    info = check_plugin("", "test")
    assert info.status == STATUS_NO_PATH


def test_check_plugin_missing_path(tmp_path):
    info = check_plugin(str(tmp_path / "nonexistent"), "test")
    assert info.status == STATUS_NO_PATH


def test_check_plugin_not_git(tmp_path):
    info = check_plugin(str(tmp_path), "test")
    assert info.status == STATUS_NOT_GIT


# --- check_plugin: config_version fallback ---


def test_check_plugin_uses_config_version_fallback(tmp_path):
    """When git has no tags, config_version is used as current version."""

    # Mock git calls to simulate: is git repo, fetch ok, no tags, but remote tags exist
    def mock_run_git(args, cwd, *, timeout=30.0):
        from unittest.mock import MagicMock

        result = MagicMock()
        if args[0] == "rev-parse":
            result.returncode = 0
            result.stdout = "true"
        elif args[0] == "fetch":
            result.returncode = 0
            result.stdout = ""
        elif args[0] == "describe":
            result.returncode = 1
            result.stdout = ""
        elif args[0] == "ls-remote":
            result.returncode = 0
            result.stdout = "abc123\trefs/tags/v1.0.0\ndef456\trefs/tags/v2.0.0\n"
        else:
            result.returncode = 1
            result.stdout = ""
        result.stderr = ""
        return result

    with patch("copilotsetup.plugin_upgrades._run_git", side_effect=mock_run_git):
        info = check_plugin(str(tmp_path), "test-plugin", config_version="0.12.1")

    assert info.status == STATUS_UPGRADABLE
    assert info.current_version == "0.12.1"
    assert info.latest_version == "v2.0.0"


def test_check_plugin_config_version_without_v_prefix(tmp_path):
    """config_version '1.0.0' is used as-is (no v prefix added) since _parse_semver handles both."""

    def mock_run_git(args, cwd, *, timeout=30.0):
        from unittest.mock import MagicMock

        result = MagicMock()
        if args[0] == "rev-parse":
            result.returncode = 0
            result.stdout = "true"
        elif args[0] == "fetch":
            result.returncode = 0
            result.stdout = ""
        elif args[0] == "describe":
            result.returncode = 1
            result.stdout = ""
        elif args[0] == "ls-remote":
            result.returncode = 0
            result.stdout = "abc123\trefs/tags/v1.0.0\n"
        else:
            result.returncode = 1
            result.stdout = ""
        result.stderr = ""
        return result

    with patch("copilotsetup.plugin_upgrades._run_git", side_effect=mock_run_git):
        info = check_plugin(str(tmp_path), "test-plugin", config_version="1.0.0")

    assert info.status == STATUS_UP_TO_DATE
    assert info.current_version == "1.0.0"


def test_check_plugin_no_tags_no_config_version(tmp_path):
    """No git tags and no config_version should return no-upstream."""

    def mock_run_git(args, cwd, *, timeout=30.0):
        from unittest.mock import MagicMock

        result = MagicMock()
        if args[0] == "rev-parse":
            result.returncode = 0
            result.stdout = "true"
        elif args[0] == "fetch":
            result.returncode = 0
            result.stdout = ""
        elif args[0] == "describe":
            result.returncode = 1
            result.stdout = ""
        elif args[0] == "ls-remote":
            result.returncode = 0
            result.stdout = "abc123\trefs/tags/v1.0.0\n"
        else:
            result.returncode = 1
            result.stdout = ""
        result.stderr = ""
        return result

    with patch("copilotsetup.plugin_upgrades._run_git", side_effect=mock_run_git):
        info = check_plugin(str(tmp_path), "test-plugin")

    assert info.status == STATUS_NO_UPSTREAM
    assert "not on a version tag" in info.detail


# --- check_plugin: ancestor tag fallback ---


def test_check_plugin_ancestor_tag(tmp_path):
    """When HEAD is ahead of a tag, --abbrev=0 should find the ancestor tag."""

    def mock_run_git(args, cwd, *, timeout=30.0):
        from unittest.mock import MagicMock

        result = MagicMock()
        if args[0] == "rev-parse":
            result.returncode = 0
            result.stdout = "true"
        elif args[0] == "fetch":
            result.returncode = 0
            result.stdout = ""
        elif args[0] == "describe" and "--exact-match" in args:
            result.returncode = 1
            result.stdout = ""
        elif args[0] == "describe" and "--abbrev=0" in args:
            result.returncode = 0
            result.stdout = "v1.1.0\n"
        elif args[0] == "ls-remote":
            result.returncode = 0
            result.stdout = "abc123\trefs/tags/v1.1.0\ndef456\trefs/tags/v1.2.0\n"
        else:
            result.returncode = 1
            result.stdout = ""
        result.stderr = ""
        return result

    with patch("copilotsetup.plugin_upgrades._run_git", side_effect=mock_run_git):
        info = check_plugin(str(tmp_path), "test-plugin")

    assert info.status == STATUS_UPGRADABLE
    assert info.current_version == "v1.1.0"
    assert info.latest_version == "v1.2.0"


# --- check_all ---


def test_check_all_passes_config_version():
    """check_all should forward 3-tuples (name, path, version)."""
    with patch("copilotsetup.plugin_upgrades.check_plugin") as mock_check:
        mock_check.return_value = PluginUpgradeInfo(name="p", path=None, status=STATUS_UP_TO_DATE)
        check_all([("p", "/some/path", "1.0.0")])
        mock_check.assert_called_once_with("/some/path", "p", "1.0.0")


def test_check_all_2_tuple_compat():
    """check_all should still accept 2-tuples for backward compatibility."""
    with patch("copilotsetup.plugin_upgrades.check_plugin") as mock_check:
        mock_check.return_value = PluginUpgradeInfo(name="p", path=None, status=STATUS_UP_TO_DATE)
        check_all([("p", "/some/path")])
        mock_check.assert_called_once_with("/some/path", "p", "")
