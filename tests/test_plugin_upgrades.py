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


# --- Tests for _git_env ---


def test_git_env_sets_terminal_prompt(monkeypatch):
    """_git_env() must set GIT_TERMINAL_PROMPT=0."""
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    from copilotsetup.plugin_upgrades import _git_env

    env = _git_env()
    assert env["GIT_TERMINAL_PROMPT"] == "0"


def test_git_env_sets_ssh_batch_mode(monkeypatch):
    """_git_env() must append -oBatchMode=yes to GIT_SSH_COMMAND."""
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GIT_SSH_COMMAND", raising=False)
    from copilotsetup.plugin_upgrades import _git_env

    env = _git_env()
    assert "-oBatchMode=yes" in env["GIT_SSH_COMMAND"]


def test_git_env_preserves_existing_ssh_command(monkeypatch):
    """_git_env() preserves an existing GIT_SSH_COMMAND wrapper."""
    monkeypatch.setenv("GIT_SSH_COMMAND", "ssh -i ~/.ssh/custom_key")
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    from copilotsetup.plugin_upgrades import _git_env

    env = _git_env()
    assert "ssh -i ~/.ssh/custom_key" in env["GIT_SSH_COMMAND"]
    assert "-oBatchMode=yes" in env["GIT_SSH_COMMAND"]


def test_git_env_uses_gh_token_env(monkeypatch):
    """_git_env() injects GH_TOKEN via GIT_CONFIG_COUNT when set."""
    monkeypatch.setenv("GH_TOKEN", "ghp_test123")
    from copilotsetup.plugin_upgrades import _git_env

    env = _git_env()
    assert env.get("GIT_CONFIG_COUNT") == "1"
    assert "x-access-token:ghp_test123@github.com" in env.get("GIT_CONFIG_KEY_0", "")


def test_git_env_uses_github_token_env(monkeypatch):
    """_git_env() falls back to GITHUB_TOKEN if GH_TOKEN not set."""
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", "ghs_fallback456")
    from copilotsetup.plugin_upgrades import _git_env

    env = _git_env()
    assert env.get("GIT_CONFIG_COUNT") == "1"
    assert "x-access-token:ghs_fallback456@github.com" in env.get("GIT_CONFIG_KEY_0", "")


def test_git_env_no_token_no_gh(monkeypatch):
    """_git_env() gracefully handles no token and no gh CLI."""
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with patch("copilotsetup.plugin_upgrades.subprocess.run", side_effect=FileNotFoundError):
        from copilotsetup.plugin_upgrades import _git_env

        env = _git_env()
        assert "GIT_CONFIG_COUNT" not in env  # no token injection
        assert env["GIT_TERMINAL_PROMPT"] == "0"  # still non-interactive


# --- Tests for _cached_latest parameter ---


def test_check_plugin_cached_latest_skips_fetch(tmp_path):
    """When _cached_latest is provided, git fetch should not be called."""
    # Create a minimal git repo with a tag
    import subprocess

    subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=str(tmp_path), capture_output=True)
    (tmp_path / "f.txt").write_text("x")
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "tag", "v1.0.0"], cwd=str(tmp_path), capture_output=True)

    from copilotsetup.plugin_upgrades import check_plugin

    # Pass _cached_latest=v2.0.0 — should detect upgrade without network
    result = check_plugin(str(tmp_path), "test", _cached_latest="v2.0.0")
    assert result.status == "upgradable"
    assert result.latest_version == "v2.0.0"
    assert result.current_version == "v1.0.0"


def test_check_plugin_cached_latest_up_to_date(tmp_path):
    """When _cached_latest matches current, status is up-to-date."""
    import subprocess

    subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=str(tmp_path), capture_output=True)
    (tmp_path / "f.txt").write_text("x")
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "tag", "v1.0.0"], cwd=str(tmp_path), capture_output=True)

    from copilotsetup.plugin_upgrades import check_plugin

    result = check_plugin(str(tmp_path), "test", _cached_latest="v1.0.0")
    assert result.status == "up-to-date"
    assert result.network_verified is True


# --- Test for fetch failure fallback to local tags ---


def test_check_plugin_fetch_fails_uses_local_tags(tmp_path):
    """When git fetch fails, should fall back to local tags."""
    import subprocess

    subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=str(tmp_path), capture_output=True)
    (tmp_path / "f.txt").write_text("x")
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "tag", "v1.0.0"], cwd=str(tmp_path), capture_output=True)
    # Add a higher local tag (simulates a previous successful fetch)
    subprocess.run(["git", "tag", "v2.0.0"], cwd=str(tmp_path), capture_output=True)

    def mock_run_git(args, cwd, *, timeout=30.0):
        if args[0] == "fetch":
            return subprocess.CompletedProcess(args=args, returncode=128, stdout="", stderr="auth failed")
        # For other commands, use real git
        return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, timeout=timeout)

    with patch("copilotsetup.plugin_upgrades._run_git", side_effect=mock_run_git):
        from copilotsetup.plugin_upgrades import check_plugin

        result = check_plugin(str(tmp_path), "test")
        assert result.status == "upgradable"
        assert result.latest_version == "v2.0.0"
        assert result.network_verified is False


def test_git_env_memoized():
    """_get_or_build_git_env should return same dict on second call."""
    import copilotsetup.plugin_upgrades as mod

    mod._cached_git_env = None
    try:
        with patch.object(mod, "_git_env", return_value={"GIT_TERMINAL_PROMPT": "0"}) as mock_git_env:
            env1 = mod._get_or_build_git_env()
            env2 = mod._get_or_build_git_env()

        assert env1 is env2
        assert mock_git_env.call_count == 1
    finally:
        mod._cached_git_env = None
