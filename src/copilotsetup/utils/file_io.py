"""Atomic JSON read/write with .bak rotation."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from contextlib import suppress
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def read_json(path: Path) -> Any:
    """Read and parse a JSON file. Returns ``None`` if missing or malformed."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.debug("read_json(%s) failed: %s", path, exc)
        return None


def write_json(path: Path, data: Any) -> None:
    """Atomically write *data* as JSON with .bak rotation.

    Writes to a temp file in the same directory, then renames.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    # Rotate existing file to .bak
    bak = path.with_suffix(path.suffix + ".bak")
    if path.exists():
        try:
            if bak.exists():
                bak.unlink()
            path.rename(bak)
        except OSError as exc:
            logger.warning("Failed to rotate %s → .bak: %s", path, exc)

    # Write to temp file, then rename (atomic on POSIX, near-atomic on Windows)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        # On Windows, target must not exist for rename
        if path.exists():
            path.unlink()
        Path(tmp).rename(path)
    except Exception:
        # Clean up temp file on failure, restore backup if possible
        with suppress(OSError):
            Path(tmp).unlink()
        if bak.exists() and not path.exists():
            with suppress(OSError):
                bak.rename(path)
        raise
