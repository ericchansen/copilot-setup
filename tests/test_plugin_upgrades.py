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


# --- check_plugin: dev-checkout (branch HEAD) ---


def test_check_plugin_dev_checkout_on_branch(tmp_path):
    """When HEAD is on a branch (not a tag), status is STATUS_LOCAL_DEV — never STATUS_UPGRADABLE.

    This is the core bug fix: the previous behavior used `git describe --abbrev=0`
    to fall back to an ancestor tag and falsely report the dev branch as upgradable.
    """
    from copilotsetup.plugin_upgrades import STATUS_LOCAL_DEV

    def mock_run_git(args, cwd, *, timeout=30.0):
        from unittest.mock import MagicMock

        result = MagicMock()
        result.stderr = ""
        if args[0] == "rev-parse":
            result.returncode = 0
            result.stdout = "true"
        elif args[0] == "fetch":
            result.returncode = 0
            result.stdout = ""
        elif args[0] == "describe" and "--exact-match" in args:
            # HEAD is not on an exact tag (we're on a dev branch).
            result.returncode = 1
            result.stdout = ""
        elif args[0] == "describe" and "--abbrev=0" in args:
            # Nearest ancestor tag is v1.1.0.
            result.returncode = 0
            result.stdout = "v1.1.0\n"
        elif args[0] == "symbolic-ref":
            # On branch feat/gh-writer.
            result.returncode = 0
            result.stdout = "feat/gh-writer\n"
        elif args[0] == "rev-list":
            # 4 commits past v1.1.0.
            result.returncode = 0
            result.stdout = "4\n"
        elif args[0] == "ls-remote":
            result.returncode = 0
            result.stdout = "abc\trefs/tags/v1.1.0\ndef\trefs/tags/v2.0.2\n"
        else:
            result.returncode = 1
            result.stdout = ""
        return result

    with patch("copilotsetup.plugin_upgrades._run_git", side_effect=mock_run_git):
        info = check_plugin(str(tmp_path), "test-plugin")

    assert info.status == STATUS_LOCAL_DEV
    assert info.upgrade_available is False  # critical: no fake upgrade arrow
    assert info.dev_branch == "feat/gh-writer"
    assert info.dev_commits_ahead == 4
    assert info.current_version == "v1.1.0"  # for context only
    assert info.latest_version == "v2.0.2"  # surfaced for detail pane
    assert info.summary == ""  # no row-level "↑ vX.Y.Z"
    assert info.dev_summary == "dev: feat/gh-writer"


def test_check_plugin_dev_checkout_no_ancestor_tag(tmp_path):
    """Dev checkout with no ancestor tag still reports STATUS_LOCAL_DEV."""
    from copilotsetup.plugin_upgrades import STATUS_LOCAL_DEV

    def mock_run_git(args, cwd, *, timeout=30.0):
        from unittest.mock import MagicMock

        result = MagicMock()
        result.stderr = ""
        if args[0] == "rev-parse":
            result.returncode = 0
            result.stdout = "true"
        elif args[0] == "fetch":
            result.returncode = 0
            result.stdout = ""
        elif args[0] == "describe":
            result.returncode = 1
            result.stdout = ""
        elif args[0] == "symbolic-ref":
            result.returncode = 0
            result.stdout = "main\n"
        elif args[0] == "rev-list":
            result.returncode = 1
            result.stdout = ""
        elif args[0] == "ls-remote":
            result.returncode = 0
            result.stdout = ""
        else:
            result.returncode = 1
            result.stdout = ""
        return result

    with patch("copilotsetup.plugin_upgrades._run_git", side_effect=mock_run_git):
        info = check_plugin(str(tmp_path), "test-plugin")

    assert info.status == STATUS_LOCAL_DEV
    assert info.dev_branch == "main"
    assert info.current_version == ""  # no ancestor tag known
    assert info.latest_version == ""
    assert info.upgrade_available is False


def test_check_plugin_detached_on_exact_tag_still_works(tmp_path):
    """Marketplace install: detached HEAD on an exact tag → normal upgrade flow."""

    def mock_run_git(args, cwd, *, timeout=30.0):
        from unittest.mock import MagicMock

        result = MagicMock()
        result.stderr = ""
        if args[0] == "rev-parse":
            result.returncode = 0
            result.stdout = "true"
        elif args[0] == "fetch":
            result.returncode = 0
            result.stdout = ""
        elif args[0] == "describe" and "--exact-match" in args:
            result.returncode = 0
            result.stdout = "v1.0.0\n"
        elif args[0] == "symbolic-ref":
            # Detached HEAD — would never be called in this path, but be defensive.
            result.returncode = 1
            result.stdout = ""
        elif args[0] == "ls-remote":
            result.returncode = 0
            result.stdout = "abc\trefs/tags/v1.0.0\ndef\trefs/tags/v2.0.0\n"
        else:
            result.returncode = 1
            result.stdout = ""
        return result

    with patch("copilotsetup.plugin_upgrades._run_git", side_effect=mock_run_git):
        info = check_plugin(str(tmp_path), "test-plugin")

    assert info.status == STATUS_UPGRADABLE
    assert info.current_version == "v1.0.0"
    assert info.latest_version == "v2.0.0"
    assert info.upgrade_available is True
    assert info.dev_branch == ""
    assert info.dev_summary == ""


def test_check_plugin_branch_at_exact_tag_still_dev(tmp_path):
    """Regression: HEAD on a branch whose tip is also at an exact tag → STATUS_LOCAL_DEV.

    Even though ``git describe --exact-match`` succeeds (branch HEAD coincides
    with a tag), ``copilot plugin update`` would do ``git pull <branch>`` rather
    than ``git checkout <newer-tag>``, so we must NOT show a one-click upgrade
    arrow. Branch state is authoritative.
    """
    from copilotsetup.plugin_upgrades import STATUS_LOCAL_DEV

    def mock_run_git(args, cwd, *, timeout=30.0):
        from unittest.mock import MagicMock

        result = MagicMock()
        result.stderr = ""
        if args[0] == "rev-parse":
            result.returncode = 0
            result.stdout = "true"
        elif args[0] == "fetch":
            result.returncode = 0
            result.stdout = ""
        elif args[0] == "symbolic-ref":
            # On branch ``main`` whose HEAD coincides with v1.0.0.
            result.returncode = 0
            result.stdout = "main\n"
        elif args[0] == "describe" and "--exact-match" in args:
            # If anything still asks for exact-match, HEAD is at v1.0.0.
            result.returncode = 0
            result.stdout = "v1.0.0\n"
        elif args[0] == "describe" and "--abbrev=0" in args:
            result.returncode = 0
            result.stdout = "v1.0.0\n"
        elif args[0] == "rev-list" and "--count" in args:
            result.returncode = 0
            result.stdout = "0\n"
        elif args[0] == "ls-remote":
            result.returncode = 0
            result.stdout = "abc\trefs/tags/v1.0.0\ndef\trefs/tags/v2.0.0\n"
        else:
            result.returncode = 1
            result.stdout = ""
        return result

    with patch("copilotsetup.plugin_upgrades._run_git", side_effect=mock_run_git):
        info = check_plugin(str(tmp_path), "test-plugin")

    assert info.status == STATUS_LOCAL_DEV, (
        f"branch HEAD that happens to coincide with a tag must still be dev, got {info.status}"
    )
    assert info.dev_branch == "main"
    assert info.upgrade_available is False
    assert info.latest_version == "v2.0.0"


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
    # Detach HEAD onto the tag — this matches what ``copilot plugin install <git-url>``
    # does in production. A repo left on a branch is now treated as STATUS_LOCAL_DEV.
    subprocess.run(["git", "checkout", "v1.0.0"], cwd=str(tmp_path), capture_output=True)

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
    subprocess.run(["git", "checkout", "v1.0.0"], cwd=str(tmp_path), capture_output=True)

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
    # Detach onto v1.0.0 so HEAD is at an exact tag (marketplace-style install).
    subprocess.run(["git", "checkout", "v1.0.0"], cwd=str(tmp_path), capture_output=True)
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
