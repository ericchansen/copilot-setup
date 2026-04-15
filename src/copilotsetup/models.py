"""Typed data models for the setup pipeline.

Replaces the untyped ``summary`` dict and loose variables with structured,
IDE-friendly dataclasses.  Every step receives a :class:`SetupContext` and
returns a :class:`StepResult`.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable

# ---------------------------------------------------------------------------
# UI protocol — structural type shared by UI and UIShim
# ---------------------------------------------------------------------------


@runtime_checkable
class UIProtocol(Protocol):
    """Minimal interface for UI objects used by library functions.

    Both :class:`~copilotsetup.ui.UI` and :class:`UIShim` satisfy this
    protocol without modification.
    """

    def item(self, name: str, status: str, detail: str = "") -> None: ...
    def print_msg(self, msg: str, status: str = "info") -> None: ...
    def confirm(self, msg: str, default: bool = ...) -> bool: ...
    def prompt(self, msg: str, default: str = "") -> str: ...
    def section(self, text: str) -> None: ...


# ---------------------------------------------------------------------------
# Item-level result (one action within a step)
# ---------------------------------------------------------------------------

Status = Literal["created", "exists", "copied", "skipped", "failed", "success", "info", "warn"]


@dataclass
class ItemResult:
    """Outcome of a single action within a step (e.g., one symlink created)."""

    name: str
    status: Status
    detail: str = ""


# ---------------------------------------------------------------------------
# Step-level result
# ---------------------------------------------------------------------------

StepStatus = Literal["ok", "skipped", "warn", "failed"]


@dataclass
class StepResult:
    """Aggregate outcome of one setup step."""

    status: StepStatus = "ok"
    items: list[ItemResult] = field(default_factory=list)
    message: str = ""

    # Convenience builders
    def item(self, name: str, status: Status, detail: str = "") -> ItemResult:
        """Add an item and return it."""
        it = ItemResult(name, status, detail)
        self.items.append(it)
        return it

    @property
    def has_failures(self) -> bool:
        return any(i.status == "failed" for i in self.items)


# ---------------------------------------------------------------------------
# Git auth state
# ---------------------------------------------------------------------------


@dataclass
class GitAuthState:
    """Detected Git/GitHub authentication capabilities."""

    gh_available: bool = False
    ssh_available: bool = False
    prefer_ssh: bool = False


# ---------------------------------------------------------------------------
# Setup context — shared state passed to every step
# ---------------------------------------------------------------------------


@dataclass
class SetupContext:
    """Immutable-ish bag of paths, flags, and shared state for the pipeline.

    Created once at the start of setup and threaded through every step.
    Steps may mutate ``plugin_managed_names``
    for downstream steps to consume.
    """

    # Paths
    repo_root: Path
    copilot_home: Path
    config_json: Path
    external_dir: Path
    repo_copilot: Path
    repo_skills: Path
    lsp_servers_json: Path
    portable_json: Path

    # CLI flags
    args: argparse.Namespace

    # Derived flags (set during preflight)
    include_clean_orphans: bool = False
    non_interactive: bool = False

    # Auth (set by git_auth step)
    auth_state: GitAuthState = field(default_factory=GitAuthState)

    # Cross-step shared state (populated by steps for downstream consumers)
    plugin_managed_names: set[str] = field(default_factory=set)
    plugin_server_names: set[str] = field(default_factory=set)
    plugins_to_install: list[dict] = field(default_factory=list)
    enabled_servers: list[dict] = field(default_factory=list)
    mcp_paths: dict[str, str] = field(default_factory=dict)
    local_skills: list[dict] = field(default_factory=list)
    lsp_count: int = 0
    lsp_skipped: list[str] = field(default_factory=list)

    # Optional real UI for interactive delegation (set by runner)
    real_ui: Any = None

    @property
    def copilot_skills(self) -> Path:
        return self.copilot_home / "skills"


# ---------------------------------------------------------------------------
# Summary — typed replacement for the 27-key dict
# ---------------------------------------------------------------------------


@dataclass
class Summary:
    """Collects results from all steps for final reporting."""

    steps: dict[str, StepResult] = field(default_factory=dict)

    def record(self, step_name: str, result: StepResult) -> None:
        """Record a step's result."""
        self.steps[step_name] = result

    @property
    def has_failures(self) -> bool:
        return any(r.status == "failed" or r.has_failures for r in self.steps.values())

    @property
    def all_items(self) -> list[ItemResult]:
        """Flatten all items across all steps."""
        return [item for r in self.steps.values() for item in r.items]

    def step_items(self, step_name: str) -> list[ItemResult]:
        """Get items for a specific step."""
        result = self.steps.get(step_name)
        return result.items if result else []


# ---------------------------------------------------------------------------
# UI shim — bridges old lib/ functions to step results
# ---------------------------------------------------------------------------


class UIShim:
    """Captures UI calls for later conversion to StepResult items.

    Old ``lib/`` functions call ``ui.item()``, ``ui.print_msg()``,
    ``ui.confirm()``, and ``ui.prompt()``.  This shim captures those calls
    as ``(name, status, detail)`` tuples.

    When a ``real_ui`` is provided, ``confirm()`` and ``prompt()`` delegate
    to it so that interactive steps still work correctly.  Without
    ``real_ui``, they return safe non-interactive defaults.

    Args:
        real_ui: Optional real UI instance to delegate interactive calls to.
    """

    def __init__(self, real_ui: Any = None) -> None:
        self.items: list[tuple[str, str, str]] = []
        self._real_ui = real_ui

    def item(self, name: str, status: str, detail: str = "") -> None:
        self.items.append((name, status, detail))

    def print_msg(self, msg: str, status: str = "info") -> None:
        self.items.append((msg, status, ""))

    def confirm(self, msg: str, default: bool = False) -> bool:
        if self._real_ui is not None:
            return self._real_ui.confirm(msg, default=default)
        return default

    def prompt(self, msg: str, default: str = "") -> str:
        if self._real_ui is not None:
            return self._real_ui.prompt(msg, default=default)
        return default

    def section(self, text: str) -> None:
        if self._real_ui is not None:
            self._real_ui.section(text)
