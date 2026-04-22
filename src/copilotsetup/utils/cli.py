"""CLI wrapper — run ``copilot`` subcommands and capture output."""

from __future__ import annotations

import logging
import subprocess

logger = logging.getLogger(__name__)


def run_copilot(*args: str, timeout: float = 30.0) -> subprocess.CompletedProcess[str]:
    """Execute ``copilot <args>`` and return the result.

    Raises ``subprocess.TimeoutExpired`` if the command exceeds *timeout*.
    Raises ``FileNotFoundError`` if the ``copilot`` binary is not on PATH.
    """
    cmd = ["copilot", *args]
    logger.debug("Running: %s", " ".join(cmd))
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
