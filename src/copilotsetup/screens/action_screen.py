"""Action execution screen — runs setup with a log panel.

Launches the action as a threaded worker, streams pipeline output to a
RichLog widget via a forwarding UI subclass, and refreshes the dashboard
when complete.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path
from typing import ClassVar

from textual import work
from textual.app import ComposeResult
from textual.binding import BindingType
from textual.screen import Screen
from textual.widgets import Footer, Header, RichLog, Static


class ActionScreen(Screen):
    """Screen that runs an action and shows log output."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "dismiss_screen", "Back"),
        ("q", "dismiss_screen", "Back"),
    ]

    def __init__(self, action: str) -> None:
        super().__init__()
        self._action = action

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(f" Running: {self._action}", id="action-title")
        yield RichLog(id="action-log", wrap=True, highlight=True)
        yield Footer()

    def on_mount(self) -> None:
        log = self.query_one("#action-log", RichLog)
        log.write(f"▶ Starting {self._action}…\n")
        self._run_action()

    @work(thread=True)
    def _run_action(self) -> None:
        """Execute the action in a background thread."""

        def log(line: str) -> None:
            self.app.call_from_thread(self._log_line, line)

        try:
            if self._action == "Setup":
                self._run_setup(log)
            else:
                log(f"  [warn] Unknown action: {self._action}")

            log(f"\n✓ {self._action} complete.")

        except Exception as exc:
            log(f"\n✗ {self._action} failed: {exc}")

        # Trigger dashboard refresh
        self.app.call_from_thread(self._finish)

    def _log_line(self, text: str) -> None:
        """Write a line to the action log (main thread)."""
        log = self.query_one("#action-log", RichLog)
        log.write(text)

    def _finish(self) -> None:
        """Called when the action completes."""
        title = self.query_one("#action-title", Static)
        title.update(f" ✓ {self._action} complete — press Escape to return")

    def action_dismiss_screen(self) -> None:
        """Return to the dashboard and refresh state."""
        self.dismiss(True)

    # -- Action implementations -----------------------------------------------

    @staticmethod
    def _run_setup(log: Callable[[str], None]) -> None:
        """Run the full setup pipeline, streaming output via ``log(line)``."""
        from copilotsetup.models import SetupContext
        from copilotsetup.platform_ops import home_dir
        from copilotsetup.runner import run_steps
        from copilotsetup.sources import discover_sources, load_source, merge_sources
        from copilotsetup.steps import ALL_STEPS
        from copilotsetup.ui import UI

        raw_sources = discover_sources()
        if not raw_sources:
            log("  [warn] No config sources registered.")
            return

        sources = [load_source(s) for s in raw_sources]
        merged = merge_sources(sources)

        copilot_home = home_dir() / ".copilot"
        repo_root = Path(__file__).resolve().parents[3]

        args = argparse.Namespace(
            non_interactive=True,
            clean_orphans=False,
            skip_session=False,
            command="setup",
        )

        ctx = SetupContext(
            repo_root=repo_root,
            copilot_home=copilot_home,
            config_json=copilot_home / "config.json",
            external_dir=repo_root / "external",
            repo_copilot=merged.instructions.parent if merged.instructions else copilot_home,
            repo_skills=merged.skill_dirs[0] if merged.skill_dirs else copilot_home / "skills",
            lsp_servers_json=Path("__merged__"),
            portable_json=merged.portable_config or Path("__none__"),
            args=args,
            include_clean_orphans=False,
            non_interactive=True,
        )

        enabled = {n: e for n, e in merged.servers.items() if n not in merged.disabled_by_default}
        ctx.enabled_servers = enabled
        ctx.merged_config = merged  # type: ignore[attr-defined]
        ctx.all_skill_dirs = merged.skill_dirs  # type: ignore[attr-defined]

        step_names = [s.name for s in ALL_STEPS]

        class _LogForwardingUI(UI):
            """UI subclass that streams item() and print_msg() to the log callback."""

            def step(self, name: str) -> None:  # type: ignore[override]
                super().step(name)
                log(f"\n▸ {name}")

            def item(self, name: str, status: str, detail: str = "") -> None:  # type: ignore[override]
                super().item(name, status, detail)
                line = f"  [{status}] {name}"
                if detail:
                    line += f" — {detail}"
                log(line)

            def print_msg(self, msg: str, status: str = "info") -> None:  # type: ignore[override]
                super().print_msg(msg, status)
                log(f"  [{status}] {msg}")

        ui = _LogForwardingUI(step_names)
        run_steps(ALL_STEPS, ctx, ui)
