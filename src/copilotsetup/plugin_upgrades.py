"""Background plugin upgrade detection — git-backed plugins, tag mode only.

Copilot CLI installs plugins as detached HEAD checkouts at a version tag (e.g.
``v0.11.2``), so detection compares the current tag against the highest semver
tag on ``origin``. Only the badge in the UI's Upgrade column is driven from
this; the actual upgrade is performed by ``copilot plugin update <name>``.

Plugins that aren't git checkouts (marketplace, direct copy) are surfaced as
``STATUS_NOT_GIT`` and produce no badge.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from copilotsetup.update_sources import is_git_checkout, run_git

if TYPE_CHECKING:
    from copilotsetup.state import PluginInfo

# Status values for a plugin upgrade check
STATUS_UP_TO_DATE = "up-to-date"
STATUS_UPGRADABLE = "upgradable"
STATUS_NOT_GIT = "not-git"
STATUS_NO_UPSTREAM = "no-upstream"
STATUS_NO_PATH = "no-path"
STATUS_ERROR = "error"


@dataclass
class PluginUpgradeInfo:
    """Result of checking one plugin for upstream updates."""

    name: str
    path: Path | None
    status: str
    detail: str = ""
    current_version: str = ""
    latest_version: str = ""

    @property
    def upgrade_available(self) -> bool:
        return self.status == STATUS_UPGRADABLE and bool(self.latest_version)

    @property
    def summary(self) -> str:
        return f"↑ {self.latest_version}" if self.upgrade_available else ""


_SEMVER_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


def _parse_semver(tag: str) -> tuple[int, int, int] | None:
    """Parse ``vM.m.p`` / ``M.m.p`` into a sortable tuple. Returns None for
    pre-release tags (``v1.0.0-rc1``) or anything non-semver.
    """
    match = _SEMVER_RE.match(tag.strip())
    if match is None:
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def _get_current_tag(path: Path) -> str | None:
    """Return the tag HEAD points at (exact match), or None if not on a tag."""
    result = run_git(
        ["describe", "--tags", "--exact-match", "HEAD"],
        path,
        timeout=5.0,
    )
    if result.returncode != 0:
        return None
    tag = result.stdout.strip()
    return tag or None


def _list_remote_tags(path: Path) -> list[str]:
    """List tag names on ``origin`` via ``git ls-remote --tags``. Skips peel
    variants (``^{}``). Returns empty list on any error.
    """
    result = run_git(["ls-remote", "--tags", "origin"], path, timeout=10.0)
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
        if not ref.startswith(prefix):
            continue
        tags.append(ref[len(prefix) :])
    return tags


def _highest_semver_tag(tags: list[str]) -> str | None:
    """Return the highest-semver tag from ``tags``, or None if none parse."""
    parsed = [(t, _parse_semver(t)) for t in tags]
    valid = [(t, v) for t, v in parsed if v is not None]
    if not valid:
        return None
    valid.sort(key=lambda item: item[1])
    return valid[-1][0]


def check_plugin_upgrade(plugin: PluginInfo) -> PluginUpgradeInfo:
    """Check one plugin for an available upgrade (tag-based comparison).

    Returns a ``PluginUpgradeInfo`` with the upgrade status. Never raises —
    network or git errors are captured in the ``detail`` field.
    """
    name = plugin.name
    install_path = Path(plugin.install_path) if plugin.install_path else None
    info = PluginUpgradeInfo(name=name, path=install_path, status=STATUS_ERROR)

    if install_path is None or not str(install_path):
        info.status = STATUS_NO_PATH
        info.detail = "plugin has no install path"
        return info

    if not install_path.exists():
        info.status = STATUS_NO_PATH
        info.detail = f"install path does not exist: {install_path}"
        return info

    if not is_git_checkout(install_path):
        info.status = STATUS_NOT_GIT
        info.detail = "install path is not a git checkout"
        return info

    current = _get_current_tag(install_path)
    if current is None:
        info.status = STATUS_NO_UPSTREAM
        info.detail = "HEAD is not on a version tag"
        return info

    info.current_version = current

    try:
        fetch = run_git(["fetch", "--tags", "--quiet"], install_path, timeout=10.0)
    except Exception as exc:
        info.status = STATUS_ERROR
        info.detail = f"git fetch raised: {exc}"
        return info

    if fetch.returncode != 0:
        info.status = STATUS_ERROR
        info.detail = f"git fetch --tags failed: {fetch.stderr.strip() or fetch.stdout.strip()}"
        return info

    remote_tags = _list_remote_tags(install_path)
    latest = _highest_semver_tag(remote_tags) if remote_tags else None
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


def check_all_plugins(
    plugins: list[PluginInfo],
    progress_cb: Callable[[int, int, str], None] | None = None,
) -> list[PluginUpgradeInfo]:
    """Run :func:`check_plugin_upgrade` serially for every installed plugin.

    ``progress_cb`` is called as ``(index, total, plugin_name)`` before each
    check so callers can update a status bar. Plugins that aren't installed
    are skipped entirely.
    """
    results: list[PluginUpgradeInfo] = []
    total = len(plugins)
    for i, plugin in enumerate(plugins, start=1):
        if progress_cb is not None:
            progress_cb(i, total, plugin.name)
        if not plugin.installed:
            continue
        results.append(check_plugin_upgrade(plugin))
    return results
