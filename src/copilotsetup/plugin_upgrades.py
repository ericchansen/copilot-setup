"""Plugin upgrade detection — git-backed plugins, tag mode.

Copilot CLI installs plugins as detached HEAD checkouts at a version tag
(e.g. ``v0.11.2``).  Detection compares the current tag against the highest
semver tag on ``origin``.

Plugins installed from a local source path that is a git checkout on a
*branch* (active dev work) are reported as ``STATUS_LOCAL_DEV`` instead of
falsely claiming they can be upgraded.  ``copilot plugin update`` only does
``git pull`` on the current branch, so an arrow that implies "click to
upgrade to vX.Y.Z" would be misleading — the user manages their own checkout.

A ``config_version`` fallback (used when no git tag describes HEAD and we
have no branch info) covers older installs whose package.json version is
the only signal.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

_SEMVER_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")

STATUS_UP_TO_DATE = "up-to-date"
STATUS_UPGRADABLE = "upgradable"
STATUS_NOT_GIT = "not-git"
STATUS_NO_UPSTREAM = "no-upstream"
STATUS_NO_PATH = "no-path"
STATUS_ERROR = "error"
# HEAD is on a branch (not detached on a tag); user is doing local dev work.
# We do not present this as upgradable because ``copilot plugin update`` would
# only ``git pull`` the branch — it cannot meaningfully "upgrade to vX.Y.Z".
STATUS_LOCAL_DEV = "local-dev"


@dataclass
class PluginUpgradeInfo:
    """Result of checking one plugin for upstream updates."""

    name: str
    path: Path | None
    status: str
    detail: str = ""
    current_version: str = ""
    latest_version: str = ""
    network_verified: bool = False
    dev_branch: str = ""
    dev_commits_ahead: int = 0

    @property
    def upgrade_available(self) -> bool:
        return self.status == STATUS_UPGRADABLE and bool(self.latest_version)

    @property
    def summary(self) -> str:
        return f"↑ {self.latest_version}" if self.upgrade_available else ""

    @property
    def dev_summary(self) -> str:
        """Human-readable dev state, e.g. ``dev: feat/x`` or empty when not on a branch."""
        if self.status != STATUS_LOCAL_DEV or not self.dev_branch:
            return ""
        return f"dev: {self.dev_branch}"


def _git_env(*, gh_token_timeout: float = 5.0) -> dict[str, str]:
    """Build a non-interactive, auth-aware git environment."""
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    ssh_cmd = env.get("GIT_SSH_COMMAND", "ssh")
    if "-oBatchMode=yes" not in ssh_cmd:
        ssh_cmd = ssh_cmd + " -oBatchMode=yes"
    env["GIT_SSH_COMMAND"] = ssh_cmd

    token = env.get("GH_TOKEN") or env.get("GITHUB_TOKEN")
    if not token:
        try:
            gh = subprocess.run(
                ["gh", "auth", "token"],
                capture_output=True,
                text=True,
                timeout=gh_token_timeout,
            )
            if gh.returncode == 0:
                token = gh.stdout.strip() or None
        except Exception:
            pass

    if token:
        try:
            count = int(env.get("GIT_CONFIG_COUNT", "0") or "0")
        except ValueError:
            count = 0
        env[f"GIT_CONFIG_KEY_{count}"] = f"url.https://x-access-token:{token}@github.com/.insteadOf"
        env[f"GIT_CONFIG_VALUE_{count}"] = "https://github.com/"
        env["GIT_CONFIG_COUNT"] = str(count + 1)

    return env


_cached_git_env: dict[str, str] | None = None


def _get_or_build_git_env() -> dict[str, str]:
    """Return a cached non-interactive git environment.

    The environment is built once per process and reused for all git
    operations within the same session.
    """
    global _cached_git_env
    if _cached_git_env is None:
        _cached_git_env = _git_env()
    return _cached_git_env


def _run_git(args: list[str], cwd: Path, *, timeout: float = 30.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout,
        env=_get_or_build_git_env(),
    )


def _parse_semver(tag: str) -> tuple[int, int, int] | None:
    match = _SEMVER_RE.match(tag.strip())
    if match is None:
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def _get_exact_tag(path: Path) -> str | None:
    """Return the tag at HEAD, or None if HEAD is not on an exact tag."""
    result = _run_git(["describe", "--tags", "--exact-match", "HEAD"], path, timeout=5.0)
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    return None


def _get_ancestor_tag(path: Path) -> str | None:
    """Return the nearest ancestor tag for HEAD (no exact-match required)."""
    result = _run_git(["describe", "--tags", "--abbrev=0", "HEAD"], path, timeout=5.0)
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    return None


def _get_head_branch(path: Path) -> str | None:
    """Return the branch HEAD is on, or None if HEAD is detached."""
    result = _run_git(["symbolic-ref", "--quiet", "--short", "HEAD"], path, timeout=5.0)
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    return None


def _get_commits_ahead(path: Path, base_ref: str) -> int:
    """Return the number of commits HEAD is ahead of ``base_ref``, or 0 on error."""
    result = _run_git(["rev-list", "--count", f"{base_ref}..HEAD"], path, timeout=5.0)
    if result.returncode != 0:
        return 0
    try:
        return int(result.stdout.strip())
    except ValueError:
        return 0


def _list_remote_tags(path: Path) -> list[str]:
    result = _run_git(["ls-remote", "--tags", "origin"], path, timeout=10.0)
    if result.returncode != 0:
        return []
    tags: list[str] = []
    for line in result.stdout.splitlines():
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        ref = parts[1].strip()
        if ref.endswith("^{}"):
            continue
        prefix = "refs/tags/"
        if ref.startswith(prefix):
            tags.append(ref[len(prefix) :])
    return tags


def _highest_semver_tag(tags: list[str]) -> str | None:
    parsed = [(t, _parse_semver(t)) for t in tags]
    valid = [(t, v) for t, v in parsed if v is not None]
    if not valid:
        return None
    valid.sort(key=lambda item: item[1])
    return valid[-1][0]


def check_plugin(
    install_path: str,
    name: str,
    config_version: str = "",
    *,
    _cached_latest: str | None = None,
) -> PluginUpgradeInfo:
    """Check one plugin for an available upgrade (tag-based comparison).

    *config_version* is the version string from ``config.json`` and is used as
    a fallback when no git tag describes HEAD.
    """
    path = Path(install_path) if install_path else None
    info = PluginUpgradeInfo(name=name, path=path, status=STATUS_ERROR)

    if path is None or not install_path:
        info.status = STATUS_NO_PATH
        info.detail = "no install path"
        return info

    if not path.exists():
        info.status = STATUS_NO_PATH
        info.detail = f"path does not exist: {path}"
        return info

    try:
        result = _run_git(["rev-parse", "--is-inside-work-tree"], path, timeout=5.0)
        if result.returncode != 0:
            raise ValueError("not a work tree")
    except Exception:
        info.status = STATUS_NOT_GIT
        info.detail = "not a git checkout"
        return info

    # Determine HEAD state. Branch is authoritative: if HEAD is on a branch,
    # we treat it as a dev install regardless of whether HEAD happens to also
    # be at an exact tag — because ``copilot plugin update`` will ``git pull``
    # the branch, not check out the tag, so we cannot promise tag-based
    # upgrades land. Only a detached HEAD on an exact tag uses the upgrade
    # flow.
    branch = _get_head_branch(path)
    exact_tag = _get_exact_tag(path) if branch is None else None

    if exact_tag is not None:
        current: str | None = exact_tag
    elif branch is None and config_version:
        # Detached HEAD with no exact tag — use config_version as a best-effort
        # current version so we can still compare against origin tags.
        v = config_version.strip()
        if _parse_semver(v) is not None:
            current = v
        elif _parse_semver(f"v{v}") is not None:
            current = f"v{v}"
        else:
            current = None
    else:
        current = None

    # Always probe remote — even in dev mode, latest_version provides useful
    # context ("origin has v2.0.2") for the detail pane.
    fetch_failed = False
    if _cached_latest is not None:
        remote_tags = [_cached_latest]
    else:
        try:
            fetch = _run_git(["fetch", "--tags", "--quiet"], path, timeout=10.0)
        except Exception:
            fetch = None
        fetch_failed = fetch is None or fetch.returncode != 0
        remote_tags = _list_remote_tags(path)
        if not remote_tags:
            local = _run_git(["tag", "-l"], path, timeout=5.0)
            remote_tags = local.stdout.strip().splitlines() if local.returncode == 0 else []

    if _cached_latest is not None or not fetch_failed:
        info.network_verified = True

    latest = _highest_semver_tag(remote_tags) if remote_tags else None

    # Branch mode → STATUS_LOCAL_DEV. We surface latest_version (when known) so
    # the detail pane can show "origin has vX.Y.Z" but the table never claims
    # this is a one-click upgrade.
    if branch is not None:
        info.status = STATUS_LOCAL_DEV
        info.dev_branch = branch
        ancestor = _get_ancestor_tag(path)
        if ancestor:
            info.current_version = ancestor
            info.dev_commits_ahead = _get_commits_ahead(path, ancestor)
        if latest is not None:
            info.latest_version = latest
        if ancestor and info.dev_commits_ahead:
            info.detail = f"branch {branch} ({info.dev_commits_ahead} past {ancestor})"
        elif ancestor:
            info.detail = f"branch {branch} (at {ancestor})"
        else:
            info.detail = f"branch {branch} (no ancestor tag)"
        return info

    if current is None:
        info.status = STATUS_NO_UPSTREAM
        info.detail = "HEAD is not on a version tag"
        return info

    info.current_version = current

    if latest is None:
        info.status = STATUS_NO_UPSTREAM
        info.detail = "no semver tags on origin"
        return info

    current_semver = _parse_semver(current)
    latest_semver = _parse_semver(latest)
    if current_semver is None or latest_semver is None:
        info.status = STATUS_NO_UPSTREAM
        info.detail = f"cannot compare {current!r} vs {latest!r}"
        return info

    if latest_semver > current_semver:
        info.status = STATUS_UPGRADABLE
        info.latest_version = latest
        info.detail = f"{current} → {latest}"
    else:
        info.status = STATUS_UP_TO_DATE
        info.detail = f"on latest tag {current}"
    return info


def check_all(
    plugins: list[tuple[str, str] | tuple[str, str, str]],
    progress_cb: Callable[[int, int, str], None] | None = None,
) -> list[PluginUpgradeInfo]:
    """Check all plugins for upgrades.

    *plugins* is a list of ``(name, install_path)`` or
    ``(name, install_path, config_version)`` tuples.
    """
    results: list[PluginUpgradeInfo] = []
    total = len(plugins)
    for i, entry in enumerate(plugins, start=1):
        match entry:
            case (name, install_path, config_version):
                pass
            case (name, install_path):
                config_version = ""
        if progress_cb is not None:
            progress_cb(i, total, name)
        results.append(check_plugin(install_path, name, config_version))
    return results
