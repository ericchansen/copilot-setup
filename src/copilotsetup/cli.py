#!/usr/bin/env python3
"""
Copilot CLI configuration, skills, and MCP/LSP server setup.

Discovers config from registered sources (~/.copilot/config-sources.json),
merges them, and runs the setup pipeline.  Idempotent — safe to re-run.

Usage:
    python setup.py               # interactive mode
    python setup.py --non-interactive
    python setup.py --clean-orphans
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows (avoids cp1252 UnicodeEncodeError with box-drawing chars)
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Ensure lib/ is importable when running from repo root
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

from copilotsetup.optional_deps import run_optional_deps
from copilotsetup.platform_ops import home_dir
from copilotsetup.sources import discover_sources, load_source, merge_sources
from copilotsetup.ui import UI

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
COPILOT_DIR = ".copilot"
SKILLS_DIR = "skills"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Copilot CLI setup, backup, restore, and skill sync",
        usage="%(prog)s [command] [options]",
    )
    sub = p.add_subparsers(dest="command")

    # Default (no subcommand) = setup, but also register it explicitly
    setup_p = sub.add_parser("setup", help="Run full setup (default)")
    setup_p.add_argument("--non-interactive", action="store_true", help="Run without prompts")
    setup_p.add_argument("--clean-orphans", action="store_true", help="Remove skills not managed by any source")

    backup_p = sub.add_parser("backup", help="Back up personalization files to OneDrive")
    backup_p.add_argument("--skip-session", action="store_true", help="Skip session-store.db (faster)")

    restore_p = sub.add_parser("restore", help="Remove setup symlinks, optionally restore from backup")
    restore_p.add_argument("--non-interactive", action="store_true", help="Skip restore prompts")

    sync_p = sub.add_parser("sync-skills", help="Adopt untracked skills from ~/.copilot/skills/")
    sync_p.add_argument("--non-interactive", action="store_true", help="Skip per-skill prompts")

    # Allow top-level flags for backward compat (no subcommand = setup)
    p.add_argument("--non-interactive", action="store_true", help=argparse.SUPPRESS)
    p.add_argument("--clean-orphans", action="store_true", help=argparse.SUPPRESS)
    p.add_argument("--skip-session", action="store_true", help=argparse.SUPPRESS)

    return p.parse_args()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    args = parse_args()
    cmd = args.command or "setup"

    if cmd == "backup":
        from copilotsetup.backup import onedrive_backup

        ui = UI(["Backup · Config Files", "Backup · Session Store"])
        ui.header("💾  Copilot Config Backup")
        onedrive_backup(ui, skip_session=args.skip_session)
        return

    if cmd == "restore":
        from copilotsetup.restore import run_restore

        ui = UI(["Scan Symlinks", "Restore from Backup"])
        ui.header("🔄  Copilot Config Restore")
        run_restore(ui, REPO_ROOT, non_interactive=args.non_interactive)
        return

    if cmd == "sync-skills":
        from copilotsetup.skills import sync_untracked_skills

        copilot_skills = home_dir() / ".copilot" / "skills"
        # Discover all skill dirs from registered sources
        sources = [load_source(s) for s in discover_sources()]
        all_skill_dirs = []
        for src in sources:
            all_skill_dirs.extend(src.skill_dirs)
        if not all_skill_dirs:
            print("No config sources with skills found. Register sources in ~/.copilot/config-sources.json")
            return
        ui = UI(["Scan Skills", "Adopt Skills"])
        ui.header("🔍  Sync Untracked Skills")
        # Use the first source's skill dir as the adoption target
        sync_untracked_skills(ui, all_skill_dirs[0], copilot_skills, non_interactive=args.non_interactive)
        return

    # Default: full setup
    _run_setup(args)


def _run_setup(args: argparse.Namespace) -> None:
    """Run the full setup flow using the step-based architecture."""
    from copilotsetup.models import SetupContext
    from copilotsetup.runner import run_steps
    from copilotsetup.steps import ALL_STEPS

    # Discover and load config sources
    raw_sources = discover_sources()
    if not raw_sources:
        print("⚠ No config sources registered in ~/.copilot/config-sources.json")
        print("  Create the file with entries like:")
        print('  [{"name": "personal", "path": "~/repos/copilot-config"}]')
        return

    sources = [load_source(s) for s in raw_sources]
    merged = merge_sources(sources)

    # Derived paths
    copilot_home = home_dir() / ".copilot"
    config_json_path = copilot_home / "config.json"
    external_dir = REPO_ROOT / "external"

    # Interactive pre-flight prompts
    include_clean_orphans = args.clean_orphans

    if not args.non_interactive:
        temp_ui = UI(["prompt"])
        if not include_clean_orphans:
            include_clean_orphans = temp_ui.confirm("Remove skills not managed by any source?")

    # Build context — paths come from merged sources, not a single repo
    ctx = SetupContext(
        repo_root=REPO_ROOT,
        copilot_home=copilot_home,
        config_json=config_json_path,
        external_dir=external_dir,
        repo_copilot=merged.instructions.parent if merged.instructions else copilot_home,
        repo_skills=merged.skill_dirs[0] if merged.skill_dirs else copilot_home / "skills",
        mcp_servers_json=Path("__merged__"),  # servers come from merged.servers, not a file
        lsp_servers_json=Path("__merged__"),  # LSP comes from merged.lsp_servers
        portable_json=merged.portable_config or Path("__none__"),
        args=args,
        include_clean_orphans=include_clean_orphans,
        non_interactive=args.non_interactive,
    )

    # Inject merged data into context for steps to consume
    ctx.enabled_servers = merged.servers  # dict[str, dict] — name → standard entry
    ctx.merged_config = merged  # type: ignore[attr-defined]
    ctx.all_skill_dirs = merged.skill_dirs  # type: ignore[attr-defined]

    # Build step name list for the UI progress bar
    step_names = [s.name for s in ALL_STEPS]
    ui = UI(step_names)
    ui.header("📦  Copilot Config & Skills Setup")

    # Print discovered sources summary
    print(f"\n  {len(sources)} config source(s) loaded:")
    for src in sources:
        parts: list[str] = []
        if src.servers:
            parts.append(f"{len(src.servers)} servers")
        if src.skill_dirs:
            skill_count = (
                sum(1 for d in src.skill_dirs for e in d.iterdir() if e.is_dir() and (e / "SKILL.md").exists())
                if src.skill_dirs
                else 0
            )
            parts.append(f"{skill_count} skills")
        if src.plugins:
            parts.append(f"{len(src.plugins)} plugins")
        if src.instructions:
            parts.append("instructions")
        if src.lsp_servers:
            parts.append("LSP config")
        if src.portable_config:
            parts.append("portable config")
        detail = f" ({', '.join(parts)})" if parts else ""
        print(f"    · {src.name}: {src.path}{detail}")
    print()

    # Run all steps
    summary = run_steps(ALL_STEPS, ctx, ui)

    # Summary — bridge to old UI summary for now
    mcp_build_items = summary.step_items("MCP · Build Servers")
    config_link_items = summary.step_items("Setup · Config Symlinks")
    config_servers = {n: e for n, e in ctx.enabled_servers.items() if n not in ctx.plugin_managed_names}

    old_summary: dict = {
        "backed_up": False,
        "backup_dir": "",
        "config_files_linked": [i.name for i in config_link_items if i.status == "created"],
        "config_files_skipped": [i.name for i in config_link_items if i.status == "skipped"],
        "config_patched": False,
        "trusted_folder_added": False,
        "skills_created": [],
        "skills_existed": [],
        "skills_skipped": [],
        "skills_failed": [],
        "mcp_servers_built": [i.name for i in mcp_build_items if i.status == "success"],
        "mcp_servers_failed": [i.name for i in mcp_build_items if i.status == "failed"],
        "mcp_env_missing": [],
        "mcp_config_generated": "MCP · Config" in summary.steps,
        "mcp_server_count": len(config_servers),
        "lsp_config_generated": "LSP · Config" in summary.steps,
        "lsp_count": ctx.lsp_count,
        "lsp_skipped": ctx.lsp_skipped,
        "plugin_junctions_cleaned": 0,
        "plugins_installed": [],
        "plugins_skipped": [],
        "plugins_failed": [],
        "plugins_updated": [],
        "plugins_update_skipped": [],
        "plugins_update_failed": [],
        "optional_installed": [],
        "optional_skipped": [],
        "optional_failed": [],
    }

    # Optional dependencies (interactive only)
    if not args.non_interactive:
        lsp_config_path = copilot_home / "lsp-config.json"
        # Find the lsp-servers.json from the first source that has it
        lsp_json_path = None
        for src in sources:
            candidate = src.copilot_dir / "lsp-servers.json"
            if candidate.is_file():
                lsp_json_path = candidate
                break
            # Fallback to root
            root_candidate = src.path / "lsp-servers.json"
            if root_candidate.is_file():
                lsp_json_path = root_candidate
                break
        if lsp_json_path:
            run_optional_deps(ui, lsp_json_path, lsp_config_path, old_summary)

    ui.summary(old_summary, ctx.enabled_servers)


if __name__ == "__main__":
    main()
