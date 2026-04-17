"""Check for and apply updates to config-source git repos.

Provides ``copilot-setup update [--check|--apply]`` subcommand.

- ``--check`` (default): for each config source that is a git checkout,
  run ``git fetch`` and report how many commits are ahead/behind its upstream.
- ``--apply``: run ``git pull --ff-only`` per source, skipping non-FF with a warning.

Non-git sources (bare directories) are skipped with a note.
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

from copilotsetup.sources import ConfigSource, discover_sources

logger = logging.getLogger(__name__)

# Status values for a single source after a check.
STATUS_UP_TO_DATE = "up-to-date"
STATUS_BEHIND = "behind"
STATUS_AHEAD = "ahead"
STATUS_DIVERGED = "diverged"
STATUS_NOT_GIT = "not-git"
STATUS_NO_UPSTREAM = "no-upstream"
STATUS_ERROR = "error"


@dataclass
class SourceUpdateInfo:
    """Result of checking one config source for updates."""

    name: str
    path: Path
    status: str
    ahead: int = 0
    behind: int = 0
    detail: str = ""

    @property
    def is_actionable(self) -> bool:
        """True when this source has commits to pull (behind upstream)."""
        return self.status == STATUS_BEHIND and self.behind > 0


def run_git(args: list[str], cwd: Path, timeout: float = 30.0) -> subprocess.CompletedProcess:
    """Run a git command in ``cwd`` and capture output."""
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def is_git_checkout(path: Path) -> bool:
    """True if ``path`` is inside a git working tree."""
    if not path.exists():
        return False
    result = run_git(["rev-parse", "--is-inside-work-tree"], path)
    return result.returncode == 0 and result.stdout.strip() == "true"


def _get_upstream_branch(path: Path) -> str | None:
    """Return the configured upstream (e.g. ``origin/main``) or None."""
    result = run_git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], path)
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def check_source(source: ConfigSource) -> SourceUpdateInfo:
    """Fetch and compare one source against its upstream."""
    info = SourceUpdateInfo(name=source.name, path=source.path, status=STATUS_ERROR)

    if not source.path.exists():
        info.status = STATUS_ERROR
        info.detail = f"path does not exist: {source.path}"
        return info

    if not is_git_checkout(source.path):
        info.status = STATUS_NOT_GIT
        info.detail = "not a git checkout"
        return info

    fetch = run_git(["fetch", "--quiet"], source.path, timeout=60.0)
    if fetch.returncode != 0:
        info.status = STATUS_ERROR
        info.detail = f"git fetch failed: {fetch.stderr.strip() or fetch.stdout.strip()}"
        return info

    upstream = _get_upstream_branch(source.path)
    if upstream is None:
        info.status = STATUS_NO_UPSTREAM
        info.detail = "no upstream branch configured"
        return info

    counts = run_git(
        ["rev-list", "--left-right", "--count", f"{upstream}...HEAD"],
        source.path,
    )
    if counts.returncode != 0:
        info.status = STATUS_ERROR
        info.detail = f"rev-list failed: {counts.stderr.strip()}"
        return info

    parts = counts.stdout.strip().split()
    if len(parts) != 2:
        info.status = STATUS_ERROR
        info.detail = f"unexpected rev-list output: {counts.stdout.strip()!r}"
        return info

    behind = int(parts[0])
    ahead = int(parts[1])
    info.behind = behind
    info.ahead = ahead

    if behind == 0 and ahead == 0:
        info.status = STATUS_UP_TO_DATE
    elif behind > 0 and ahead == 0:
        info.status = STATUS_BEHIND
    elif behind == 0 and ahead > 0:
        info.status = STATUS_AHEAD
    else:
        info.status = STATUS_DIVERGED

    return info


def apply_source(info: SourceUpdateInfo) -> tuple[bool, str]:
    """Attempt a fast-forward pull on a source known to be behind.

    Returns ``(ok, detail)``.
    """
    if info.status != STATUS_BEHIND:
        return False, f"skip: status is {info.status}"

    result = run_git(["pull", "--ff-only"], info.path, timeout=120.0)
    if result.returncode == 0:
        first_line = result.stdout.strip().splitlines()[0] if result.stdout.strip() else "updated"
        return True, first_line
    err = result.stderr.strip() or result.stdout.strip() or "git pull failed"
    return False, err


def check_all() -> list[SourceUpdateInfo]:
    """Check every registered config source."""
    return [check_source(src) for src in discover_sources()]


# -- CLI entry point -----------------------------------------------------------


def _fmt_row(info: SourceUpdateInfo) -> str:
    """Format one row for table output."""
    if info.status == STATUS_BEHIND:
        counts = f"↓{info.behind}"
    elif info.status == STATUS_AHEAD:
        counts = f"↑{info.ahead}"
    elif info.status == STATUS_DIVERGED:
        counts = f"↓{info.behind} ↑{info.ahead}"
    else:
        counts = "-"
    detail = info.detail or ""
    return f"  {info.name:<20} {info.status:<13} {counts:<10} {detail}"


def _print_report(results: list[SourceUpdateInfo]) -> None:
    """Print a short summary table to stdout."""
    if not results:
        print("No config sources registered (~/.copilot/config-sources.json is empty or missing).")
        return
    print(f"  {'SOURCE':<20} {'STATUS':<13} {'COUNTS':<10} DETAIL")
    print(f"  {'-' * 20} {'-' * 13} {'-' * 10} {'-' * 40}")
    for r in results:
        print(_fmt_row(r))


def run_cli(apply: bool = False) -> int:
    """Entry point for ``copilot-setup update [--apply]``.

    Returns a process exit code (0 = ok, 1 = some source had an error).
    """
    results = check_all()
    _print_report(results)

    exit_code = 0
    if any(r.status == STATUS_ERROR for r in results):
        exit_code = 1

    if not apply:
        behind_count = sum(1 for r in results if r.is_actionable)
        if behind_count:
            print()
            print(f"{behind_count} source(s) behind upstream. Run with --apply to pull.")
        return exit_code

    # Apply phase
    actionable = [r for r in results if r.is_actionable]
    if not actionable:
        print()
        print("Nothing to apply.")
        return exit_code

    print()
    print("Applying updates:")
    for info in actionable:
        ok, detail = apply_source(info)
        marker = "✓" if ok else "✗"
        print(f"  {marker} {info.name}: {detail}")
        if not ok:
            exit_code = 1

    return exit_code
