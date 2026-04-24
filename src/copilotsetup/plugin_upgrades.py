"""Plugin upgrade detection — git-backed plugins, tag mode.

Copilot CLI installs plugins as detached HEAD checkouts at a version tag
(e.g. ``v0.11.2``).  Detection compares the current tag against the highest
semver tag on ``origin``.

Local plugins living on a regular branch are also supported: the nearest
ancestor tag (via ``git describe --tags --abbrev=0``) is used as the current
version.  A ``config_version`` fallback covers repos with no local tags.
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
    """Return the version tag for HEAD.

    Tries ``--exact-match`` first (detached-HEAD installs), then falls back to
    ``--abbrev=0`` which finds the nearest ancestor tag (branch-based repos).
    """
    result = _run_git(["describe", "--tags", "--exact-match", "HEAD"], path, timeout=5.0)
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    # Fallback: nearest ancestor tag (works when HEAD is ahead of a tag)
    result = _run_git(["describe", "--tags", "--abbrev=0", "HEAD"], path, timeout=5.0)
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    return None


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

    # Fetch tags from origin FIRST so newly-installed plugins have tags to
    # compare against (previously this happened after tag detection, causing
    # repos with no local tags to bail out early).
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

    # Detect current version: exact tag → nearest ancestor tag → config.json
    current = _get_current_tag(path)
    if current is None and config_version:
        # Synthesize a tag-like string so semver comparison works
        v = config_version.strip()
        if _parse_semver(v) is not None:
            current = v
        elif _parse_semver(f"v{v}") is not None:
            current = f"v{v}"
    if current is None:
        info.status = STATUS_NO_UPSTREAM
        info.detail = "HEAD is not on a version tag"
        return info

    info.current_version = current

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
