"""Tests for the update_sources module — check/apply git updates on config sources."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from copilotsetup.sources import ConfigSource
from copilotsetup.update_sources import (
    STATUS_AHEAD,
    STATUS_BEHIND,
    STATUS_DIVERGED,
    STATUS_ERROR,
    STATUS_NO_UPSTREAM,
    STATUS_NOT_GIT,
    STATUS_UP_TO_DATE,
    apply_source,
    check_source,
    run_cli,
)


def _git(cwd: Path, *args: str) -> str:
    """Run git in ``cwd``, return stdout; raise on error."""
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def _init_repo(path: Path, bare: bool = False) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if bare:
        _git(path, "init", "--bare", "--initial-branch=main")
        return
    _git(path, "init", "--initial-branch=main")
    _git(path, "config", "user.email", "test@test.invalid")
    _git(path, "config", "user.name", "Test")
    _git(path, "commit", "--allow-empty", "-m", "initial")


def _commit(path: Path, name: str) -> None:
    (path / name).write_text(name, "utf-8")
    _git(path, "add", name)
    _git(path, "commit", "-m", f"add {name}")


@pytest.fixture
def remote_and_clone(tmp_path: Path) -> tuple[Path, Path]:
    """Create a bare remote with one commit, cloned to a working tree."""
    remote = tmp_path / "remote.git"
    seed = tmp_path / "seed"
    _init_repo(seed)
    _init_repo(remote, bare=True)
    _git(seed, "remote", "add", "origin", str(remote))
    _git(seed, "push", "-u", "origin", "main")

    clone = tmp_path / "clone"
    _git(tmp_path, "clone", str(remote), str(clone))
    _git(clone, "config", "user.email", "test@test.invalid")
    _git(clone, "config", "user.name", "Test")
    return remote, clone


def test_check_non_git_path(tmp_path: Path) -> None:
    bare_dir = tmp_path / "plain"
    bare_dir.mkdir()
    info = check_source(ConfigSource(name="x", path=bare_dir))
    assert info.status == STATUS_NOT_GIT


def test_check_missing_path(tmp_path: Path) -> None:
    info = check_source(ConfigSource(name="x", path=tmp_path / "missing"))
    assert info.status == STATUS_ERROR


def test_check_up_to_date(remote_and_clone: tuple[Path, Path]) -> None:
    _, clone = remote_and_clone
    info = check_source(ConfigSource(name="c", path=clone))
    assert info.status == STATUS_UP_TO_DATE
    assert info.ahead == 0
    assert info.behind == 0


def test_check_behind(remote_and_clone: tuple[Path, Path], tmp_path: Path) -> None:
    remote, clone = remote_and_clone
    # Push a new commit to remote via another clone
    other = tmp_path / "other"
    _git(tmp_path, "clone", str(remote), str(other))
    _git(other, "config", "user.email", "test@test.invalid")
    _git(other, "config", "user.name", "Test")
    _commit(other, "new.txt")
    _git(other, "push", "origin", "main")

    info = check_source(ConfigSource(name="c", path=clone))
    assert info.status == STATUS_BEHIND
    assert info.behind == 1
    assert info.ahead == 0
    assert info.is_actionable


def test_check_ahead(remote_and_clone: tuple[Path, Path]) -> None:
    _, clone = remote_and_clone
    _commit(clone, "local.txt")
    info = check_source(ConfigSource(name="c", path=clone))
    assert info.status == STATUS_AHEAD
    assert info.ahead == 1
    assert info.behind == 0


def test_check_diverged(remote_and_clone: tuple[Path, Path], tmp_path: Path) -> None:
    remote, clone = remote_and_clone
    other = tmp_path / "other"
    _git(tmp_path, "clone", str(remote), str(other))
    _git(other, "config", "user.email", "test@test.invalid")
    _git(other, "config", "user.name", "Test")
    _commit(other, "remote.txt")
    _git(other, "push", "origin", "main")

    _commit(clone, "local.txt")

    info = check_source(ConfigSource(name="c", path=clone))
    assert info.status == STATUS_DIVERGED
    assert info.ahead == 1
    assert info.behind == 1
    assert not info.is_actionable


def test_check_no_upstream(tmp_path: Path) -> None:
    repo = tmp_path / "no-upstream"
    _init_repo(repo)
    info = check_source(ConfigSource(name="c", path=repo))
    assert info.status == STATUS_NO_UPSTREAM


def test_apply_source_ff(remote_and_clone: tuple[Path, Path], tmp_path: Path) -> None:
    remote, clone = remote_and_clone
    other = tmp_path / "other"
    _git(tmp_path, "clone", str(remote), str(other))
    _git(other, "config", "user.email", "test@test.invalid")
    _git(other, "config", "user.name", "Test")
    _commit(other, "new.txt")
    _git(other, "push", "origin", "main")

    info = check_source(ConfigSource(name="c", path=clone))
    assert info.status == STATUS_BEHIND

    ok, _detail = apply_source(info)
    assert ok is True
    assert (clone / "new.txt").exists()


def test_apply_skips_non_behind(remote_and_clone: tuple[Path, Path]) -> None:
    _, clone = remote_and_clone
    info = check_source(ConfigSource(name="c", path=clone))
    ok, detail = apply_source(info)
    assert ok is False
    assert "skip" in detail


def test_run_cli_empty(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr("copilotsetup.sources.home_dir", lambda: tmp_path)
    rc = run_cli(apply=False)
    assert rc == 0
    out = capsys.readouterr().out
    assert "No config sources" in out
