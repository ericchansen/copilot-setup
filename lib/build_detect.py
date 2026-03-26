"""Auto-detect build system from directory contents."""

from __future__ import annotations

from pathlib import Path


def detect_build_commands(path: Path) -> list[str]:
    """Detect build commands for a project directory.

    Checks for common build system marker files and returns the
    appropriate install/build commands.  Returns an empty list when
    no recognised build system is found.
    """
    if (path / "package.json").is_file():
        return ["npm install", "npm run build"]

    if (path / "pyproject.toml").is_file() or (path / "setup.py").is_file():
        return ["python -m pip install -e ."]

    if (path / "Cargo.toml").is_file():
        return ["cargo build --release"]

    if (path / "go.mod").is_file():
        return ["go build ./..."]

    if (path / "Makefile").is_file():
        return ["make"]

    return []
