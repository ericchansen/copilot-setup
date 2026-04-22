"""Cross-platform filesystem operations for Copilot CLI setup.

Provides OS-specific detection of junctions/symlinks and LSP binary
validation.  All write/link-creation functions have been removed — this
module is read-only.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

IS_WINDOWS = sys.platform == "win32"
_FILE_ATTRIBUTE_REPARSE_POINT = 0x400


# ---------------------------------------------------------------------------
# Link detection (read-only)
# ---------------------------------------------------------------------------


def is_link(path: Path) -> bool:
    """Return True if *path* is a symlink or a Windows junction (reparse point)."""
    if path.is_symlink():
        return True
    if IS_WINDOWS:
        try:
            attrs = path.stat(follow_symlinks=False).st_file_attributes  # type: ignore[attr-defined]
            return bool(attrs & _FILE_ATTRIBUTE_REPARSE_POINT)
        except (OSError, AttributeError):
            return False
    return False


def get_link_target(path: Path) -> Path | None:
    """Return the target of a symlink/junction, or None if not a link."""
    if not is_link(path):
        return None
    try:
        return path.readlink()
    except OSError:
        try:
            resolved = path.resolve()
            if resolved != path:
                return resolved
        except OSError:
            pass
    return None


# ---------------------------------------------------------------------------
# LSP binary validation
# ---------------------------------------------------------------------------


def validate_lsp_binary(command: str, args: list[str]) -> bool:
    """Check that an LSP server binary exists and stays alive on startup."""
    resolved = shutil.which(command)
    if resolved is None:
        return False

    cmd_list = _build_lsp_command(resolved, args)

    try:
        proc = subprocess.Popen(
            cmd_list,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if IS_WINDOWS else 0,
        )

        # Keep stdin open — LSP servers exit immediately on EOF.
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            # Still running after 2 s → binary is functional.
            proc.kill()
            proc.wait()
            return True

        # Exited within 2 s — functional only if exit code is 0.
        return proc.returncode == 0

    except OSError:
        return False


def _build_lsp_command(resolved: str, args: list[str]) -> list[str]:
    """Translate a resolved binary path into the command list to execute.

    On Windows, npm shims (``.ps1`` / ``.cmd``) need special handling.
    """
    if not IS_WINDOWS:
        return [resolved, *args]

    rp = Path(resolved)
    suffix = rp.suffix.lower()

    if suffix == ".ps1":
        cmd_sibling = rp.with_suffix(".cmd")
        if cmd_sibling.is_file():
            args_str = " ".join(str(a) for a in args)
            return ["cmd", "/c", f"{cmd_sibling} {args_str}".strip()]
        args_str = " ".join(str(a) for a in args)
        return ["pwsh", "-NoProfile", "-File", str(rp), *args]

    if suffix in (".cmd", ".bat"):
        args_str = " ".join(str(a) for a in args)
        return ["cmd", "/c", f"{rp} {args_str}".strip()]

    return [resolved, *args]
