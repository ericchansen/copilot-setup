"""Interactive onboarding — create config-sources.json and scaffold a config source.

Called when a user runs ``copilot-setup`` for the first time (no sources registered)
or explicitly via ``copilot-setup init``.
"""

from __future__ import annotations

import json
from pathlib import Path

from copilotsetup.platform_ops import home_dir
from copilotsetup.sources import SOURCES_FILE
from copilotsetup.ui import BOLD, CYAN, GRAY, GREEN, RESET, UI

_COPILOT_DIR = ".copilot"

# Files created during scaffold
_SCAFFOLD_FILES: dict[str, str] = {
    "mcp.json": json.dumps({"mcpServers": {}}, indent=2) + "\n",
    "plugins.json": json.dumps({"plugins": {}}, indent=2) + "\n",
    "copilot-instructions.md": "# Copilot Instructions\n\nAdd your custom instructions here.\n",
    "local.json": json.dumps({"paths": {}, "plugins": {}}, indent=2) + "\n",
}


def sources_file() -> Path:
    """Path to ``~/.copilot/config-sources.json``."""
    return home_dir() / _COPILOT_DIR / SOURCES_FILE


def _default_source_path() -> str:
    """Suggest a default config source path based on the home directory."""
    return str(Path("~/repos/copilot-config"))


def run_init(ui: UI, *, non_interactive: bool = False) -> bool:
    """Interactive onboarding wizard. Returns True if a source was registered."""
    sf = sources_file()

    if sf.exists():
        existing = _load_existing(sf)
        if existing:
            ui.print_msg(
                f"config-sources.json already has {len(existing)} source(s) registered.",
                "info",
            )
            for src in existing:
                ui.print_msg(f"  {src['name']}: {src['path']}", "info")
            if non_interactive:
                return False
            if not ui.confirm("Add another config source?"):
                return False

    if non_interactive:
        print("⚠ No config sources registered. Run `copilot-setup init` interactively.")
        return False

    # ── Collect source info ──────────────────────────────────────────────
    print()
    print(f"  {BOLD}Let's register a config source.{RESET}")
    print(f"  {GRAY}A config source is a directory (usually a git repo) that holds your{RESET}")
    print(f"  {GRAY}MCP servers, skills, and instructions in a .copilot/ subdirectory.{RESET}")
    print()

    name = ui.prompt("Source name", default="personal")
    if not name:
        return False

    default_path = _default_source_path()
    raw_path = ui.prompt("Source path", default=default_path)
    if not raw_path:
        return False

    source_path = Path(raw_path).expanduser().resolve()

    # ── Scaffold if the directory doesn't exist yet ──────────────────────
    created_dir = False
    scaffolded = False
    if not source_path.exists():
        if ui.confirm(f"Directory doesn't exist. Create {source_path}?", default=True):
            source_path.mkdir(parents=True, exist_ok=True)
            created_dir = True
        else:
            print(f"  {GRAY}Registering anyway — you can create it later.{RESET}")

    if source_path.is_dir():
        copilot_dir = source_path / _COPILOT_DIR
        if not copilot_dir.exists() and ui.confirm(
            "Scaffold .copilot/ directory with starter files?", default=True
        ):
            scaffolded = _scaffold_source(copilot_dir)

    # ── Write config-sources.json ────────────────────────────────────────
    _register_source(sf, name, raw_path)

    # ── Report what happened ─────────────────────────────────────────────
    print()
    ui.print_msg(f"Registered source '{name}' → {raw_path}", "success")
    if created_dir:
        ui.print_msg(f"Created directory {source_path}", "success")
    if scaffolded:
        ui.print_msg("Scaffolded .copilot/ with starter files", "success")
        copilot_dir = source_path / _COPILOT_DIR
        for filename in sorted(_SCAFFOLD_FILES):
            print(f"    {GRAY}  └ {copilot_dir / filename}{RESET}")
        skills_dir = copilot_dir / "skills"
        print(f"    {GRAY}  └ {skills_dir}/{RESET}")

    print()
    print(f"  {GREEN}✓{RESET} Config source registered. Run {CYAN}copilot-setup{RESET} to continue setup.")
    print()
    return True


def _load_existing(sf: Path) -> list[dict]:
    """Load existing entries from config-sources.json."""
    try:
        data = json.loads(sf.read_text("utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _register_source(sf: Path, name: str, raw_path: str) -> None:
    """Add an entry to config-sources.json (creating it if needed)."""
    sf.parent.mkdir(parents=True, exist_ok=True)

    existing = _load_existing(sf) if sf.exists() else []
    existing.append({"name": name, "path": raw_path})
    sf.write_text(json.dumps(existing, indent=2) + "\n", "utf-8")


def _scaffold_source(copilot_dir: Path) -> bool:
    """Create the .copilot/ directory with starter files. Returns True on success."""
    try:
        copilot_dir.mkdir(parents=True, exist_ok=True)

        for filename, content in _SCAFFOLD_FILES.items():
            filepath = copilot_dir / filename
            if not filepath.exists():
                filepath.write_text(content, "utf-8")

        # Create skills directory
        skills_dir = copilot_dir / "skills"
        skills_dir.mkdir(exist_ok=True)

        return True
    except OSError:
        return False
