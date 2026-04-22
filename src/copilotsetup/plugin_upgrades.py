"""Plugin upgrade detection — git-backed plugins, tag mode.

Copilot CLI installs plugins as detached HEAD checkouts at a version tag
(e.g. ``v0.11.2``).  Detection compares the current tag against the highest
semver tag on ``origin``.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

_SEMVER_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")

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


def _run_git(args: list[str], cwd: Path, *, timeout: float = 30.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _parse_semver(tag: str) -> tuple[int, int, int] | None:
    match = _SEMVER_RE.match(tag.strip())
    if match is None:
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def _get_current_tag(path: Path) -> str | None:
    result = _run_git(["describe", "--tags", "--exact-match", "HEAD"], path, timeout=5.0)
    if result.returncode != 0:
        return None
    tag = result.stdout.strip()
    return tag or None


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


def check_plugin(install_path: str, name: str) -> PluginUpgradeInfo:
    """Check one plugin for an available upgrade (tag-based comparison)."""
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

    current = _get_current_tag(path)
    if current is None:
        info.status = STATUS_NO_UPSTREAM
        info.detail = "HEAD is not on a version tag"
        return info

    info.current_version = current

    try:
        fetch = _run_git(["fetch", "--tags", "--quiet"], path, timeout=10.0)
    except Exception as exc:
        info.status = STATUS_ERROR
        info.detail = f"git fetch raised: {exc}"
        return info

    if fetch.returncode != 0:
        info.status = STATUS_ERROR
        info.detail = f"git fetch failed: {(fetch.stderr or fetch.stdout).strip()}"
        return info

    remote_tags = _list_remote_tags(path)
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


def check_all(
    plugins: list[tuple[str, str]],
    progress_cb: Callable[[int, int, str], None] | None = None,
) -> list[PluginUpgradeInfo]:
    """Check all plugins for upgrades. ``plugins`` is a list of (name, install_path)."""
    results: list[PluginUpgradeInfo] = []
    total = len(plugins)
    for i, (name, install_path) in enumerate(plugins, start=1):
        if progress_cb is not None:
            progress_cb(i, total, name)
        results.append(check_plugin(install_path, name))
    return results
