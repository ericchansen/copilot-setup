"""Tests for plugin_upgrades.check_plugin_upgrade with real local git repos."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from copilotsetup.plugin_upgrades import (
    STATUS_NO_PATH,
    STATUS_NO_UPSTREAM,
    STATUS_NOT_GIT,
    STATUS_UP_TO_DATE,
    STATUS_UPGRADABLE,
    _highest_semver_tag,
    _parse_semver,
    check_all_plugins,
    check_plugin_upgrade,
)
from copilotsetup.state import PluginInfo


def _git(cwd: Path, *args: str) -> None:
    """Run git with minimal config, raising on failure."""
    env_args = [
        "-c",
        "user.email=test@example.com",
        "-c",
        "user.name=test",
        "-c",
        "commit.gpgsign=false",
        "-c",
        "init.defaultBranch=main",
    ]
    subprocess.run(
        ["git", *env_args, *args],
        cwd=str(cwd),
        check=True,
        capture_output=True,
        text=True,
    )


def _make_commit(cwd: Path, message: str, filename: str = "file.txt") -> None:
    (cwd / filename).write_text(message)
    _git(cwd, "add", filename)
    _git(cwd, "commit", "-m", message)


@pytest.fixture
def upstream_repo(tmp_path: Path) -> Path:
    """A bare repo to serve as the `origin` remote."""
    upstream = tmp_path / "upstream.git"
    upstream.mkdir()
    _git(upstream, "init", "--bare", "--initial-branch=main")
    return upstream


@pytest.fixture
def plugin_checkout(tmp_path: Path, upstream_repo: Path) -> Path:
    """A git checkout tracking the upstream bare repo on main."""
    checkout = tmp_path / "plugin"
    checkout.mkdir()
    _git(checkout, "init", "--initial-branch=main")
    _git(checkout, "remote", "add", "origin", str(upstream_repo))
    _make_commit(checkout, "initial")
    _git(checkout, "push", "-u", "origin", "main")
    return checkout


def _plugin(name: str, path: Path | str, installed: bool = True) -> PluginInfo:
    return PluginInfo(
        name=name,
        source="test",
        installed=installed,
        install_path=str(path),
    )


class TestCheckPluginUpgrade:
    def test_no_install_path_returns_no_path(self, tmp_path: Path) -> None:
        plugin = _plugin("empty", "")
        result = check_plugin_upgrade(plugin)
        assert result.status == STATUS_NO_PATH
        assert not result.upgrade_available

    def test_missing_directory_returns_no_path(self, tmp_path: Path) -> None:
        plugin = _plugin("missing", tmp_path / "does-not-exist")
        result = check_plugin_upgrade(plugin)
        assert result.status == STATUS_NO_PATH

    def test_non_git_dir_returns_not_git(self, tmp_path: Path) -> None:
        plain = tmp_path / "plain"
        plain.mkdir()
        (plain / "readme.md").write_text("hi")
        result = check_plugin_upgrade(_plugin("plain", plain))
        assert result.status == STATUS_NOT_GIT

    def test_on_branch_not_tag_returns_no_upstream(self, plugin_checkout: Path) -> None:
        # plugin_checkout is on `main`, not on a tag — we no longer support
        # branch-mode detection, so this should report NO_UPSTREAM.
        result = check_plugin_upgrade(_plugin("p", plugin_checkout))
        assert result.status == STATUS_NO_UPSTREAM
        assert not result.upgrade_available
        assert result.summary == ""


class TestCheckAllPlugins:
    def test_skips_uninstalled(self, plugin_checkout: Path) -> None:
        installed = _plugin("p1", plugin_checkout, installed=True)
        not_installed = _plugin("p2", "/nowhere", installed=False)
        results = check_all_plugins([installed, not_installed])
        names = [r.name for r in results]
        assert "p1" in names
        assert "p2" not in names

    def test_progress_callback_fires(self, plugin_checkout: Path) -> None:
        calls: list[tuple[int, int, str]] = []
        check_all_plugins(
            [_plugin("p", plugin_checkout)],
            progress_cb=lambda i, n, name: calls.append((i, n, name)),
        )
        assert calls == [(1, 1, "p")]


class TestParseSemver:
    def test_with_v_prefix(self) -> None:
        assert _parse_semver("v1.2.3") == (1, 2, 3)

    def test_without_v_prefix(self) -> None:
        assert _parse_semver("1.2.3") == (1, 2, 3)

    def test_pre_release_returns_none(self) -> None:
        assert _parse_semver("v1.2.3-rc1") is None
        assert _parse_semver("1.0.0-beta") is None

    def test_branch_name_returns_none(self) -> None:
        assert _parse_semver("main") is None
        assert _parse_semver("feature/x") is None

    def test_highest_semver_picks_max(self) -> None:
        tags = ["v0.9.0", "v0.10.0", "v0.11.2", "v0.11.0", "main", "v0.5.1"]
        assert _highest_semver_tag(tags) == "v0.11.2"

    def test_highest_semver_no_valid(self) -> None:
        assert _highest_semver_tag(["main", "develop"]) is None


@pytest.fixture
def tag_plugin_checkout(tmp_path: Path, upstream_repo: Path) -> Path:
    """A clone with three semver tags (v1.0.0, v1.1.0, v1.2.0), checked out at
    v1.0.0 in detached HEAD. Tags are pushed to upstream so ls-remote sees them.
    """
    work = tmp_path / "work"
    work.mkdir()
    _git(work, "init", "--initial-branch=main")
    _git(work, "remote", "add", "origin", str(upstream_repo))
    for v in ("v1.0.0", "v1.1.0", "v1.2.0"):
        _make_commit(work, f"commit for {v}")
        _git(work, "tag", v)
    _git(work, "push", "origin", "main")
    _git(work, "push", "--tags", "origin")

    # Now make a fresh clone, checkout v1.0.0 in detached HEAD.
    checkout = tmp_path / "plugin-tag"
    subprocess.run(
        ["git", "clone", str(upstream_repo), str(checkout)],
        check=True,
        capture_output=True,
    )
    _git(checkout, "checkout", "v1.0.0")
    return checkout


class TestTagModeUpgrade:
    def test_upgradable_via_tags(self, tag_plugin_checkout: Path) -> None:
        result = check_plugin_upgrade(_plugin("p", tag_plugin_checkout))
        assert result.status == STATUS_UPGRADABLE, result.detail
        assert result.current_version == "v1.0.0"
        assert result.latest_version == "v1.2.0"
        assert result.upgrade_available
        assert result.summary == "↑ v1.2.0"
        assert "v1.0.0" in result.detail and "v1.2.0" in result.detail

    def test_up_to_date_on_latest_tag(self, tag_plugin_checkout: Path) -> None:
        _git(tag_plugin_checkout, "checkout", "v1.2.0")
        result = check_plugin_upgrade(_plugin("p", tag_plugin_checkout))
        assert result.status == STATUS_UP_TO_DATE, result.detail
        assert result.current_version == "v1.2.0"
        assert not result.upgrade_available
        assert result.summary == ""

    def test_detached_no_tags_returns_no_upstream(self, tmp_path: Path, upstream_repo: Path) -> None:
        # Clone with no tags, detach HEAD on the only commit.
        work = tmp_path / "work"
        work.mkdir()
        _git(work, "init", "--initial-branch=main")
        _git(work, "remote", "add", "origin", str(upstream_repo))
        _make_commit(work, "only")
        _git(work, "push", "-u", "origin", "main")

        checkout = tmp_path / "plugin-detached"
        subprocess.run(
            ["git", "clone", str(upstream_repo), str(checkout)],
            check=True,
            capture_output=True,
        )
        # Detach HEAD without landing on a tag.
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(checkout),
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        # Wipe the local branch ref so there's no upstream tracking.
        _git(checkout, "checkout", "--detach", sha)
        _git(checkout, "branch", "-D", "main")

        result = check_plugin_upgrade(_plugin("p", checkout))
        assert result.status == STATUS_NO_UPSTREAM
        assert not result.upgrade_available
        assert result.summary == ""
