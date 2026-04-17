# AGENTS.md — copilot-setup

## Repository Purpose

This is the **configuration engine** for GitHub Copilot CLI, presented as a **Textual TUI
dashboard**. It discovers, merges, and deploys configuration from multiple sources. The
engine contains NO configuration data — all data (servers, plugins, skills, instructions)
comes from config source repos.

## Architecture

- **Entry point**: `app.py` → `main()` → `CopilotSetupApp`
- **State layer**: `state.py` computes desired state (from merged sources) + actual state (filesystem)
- **Source discovery**: `sources.py` reads `~/.copilot/config-sources.json`
- **Pipeline**: Ordered steps defined in `copilotsetup/steps/__init__.py`
- **Step protocol**: Each step has `name: str`, `check(ctx) -> bool`, `run(ctx) -> StepResult`
- **Action screen**: `screens/action_screen.py` runs setup in a threaded worker
- **Tab widgets**: `widgets/` — populate functions for 5 DataTable tabs

## Key Design Decisions

- **Engine/data separation**: No `mcp-servers.json`, no skills, no instructions in this repo
- **Desired + actual state**: `state.py` computes what should exist AND what does exist, surfacing drift
- **Threaded workers**: State loading and actions run in `@work(thread=True)`, UI updates via `call_from_thread()`
- **Steps stay decoupled from Textual**: Steps return `StepResult` via protocol — never import Textual
- **Additive merging**: MCP servers, plugins, and skills are collected from ALL sources
- **First-wins merging**: Instructions, portable config, and LSP config take the first source
- **Server deduplication**: By name — first occurrence wins
- **Category field stripped**: `load_source()` removes `category` from server definitions
- **Legacy support**: Sources using `.copilot/` subdir layout are auto-detected
- **Platform ops**: Windows junctions require special handling — always use `platform_ops.is_link()` / `remove_link()`, never `is_symlink()` / `unlink()` directly
- **Path prefix matching**: Always use separator-boundary checks (append `/` before `startswith`) to prevent `/agency` matching `/agency2`. See `_under_prefix()` in `steps/skills.py`.
- **Agency naming**: When an MCP server overlaps with an Agency built-in, use Agency's
  name so dedup works (e.g., `msft-learn` not `microsoft-learn`). Agency built-in names:
  `ado`, `bluebird`, `cloudbuild`, `es-chat`, `icm`, `kusto`, `local`, `m365-copilot`,
  `m365-user`, `mail`, `calendar`, `msft-learn`, `npx`, `planner`, `remote`,
  `security-context`, `teams`, `word`, `workiq`

## File Conventions

When editing:
- `app.py` — TUI entry point. Tabbed dashboard with threaded worker loading.
- `state.py` — Data layer. Computes `DashboardState` from merged sources + filesystem.
- `screens/action_screen.py` — Runs setup. Creates SetupContext and uses `runner.run_steps()`.
- `widgets/` — Pure populate functions that fill DataTable widgets from `DashboardState`.
- `sources.py` — Core merging logic. If you change merge strategies, update tests.
- `copilotsetup/steps/` — Each step reads from `ctx` (SetupContext). Steps must not import
  data directly; they get it from the context which is populated from merged sources.

## Pre-commit / Pre-push Checklist (MANDATORY)

**CI runs ALL THREE checks. Every one must pass locally before committing.**

```bash
# 1. Lint — catches code errors, unused imports, bad patterns
python -m ruff check .

# 2. Format — catches formatting violations (trailing whitespace, line length, etc.)
python -m ruff format --check .
# Fix formatting issues with: python -m ruff format .

# 3. Tests — all tests must pass
python -m pytest tests/ -v
```

**DO NOT skip `ruff format --check`.** It is a separate CI job from `ruff check` and
will fail the PR independently. Running `ruff check` alone is NOT sufficient.

**Quick one-liner for the full CI check:**
```bash
python -m ruff check . && python -m ruff format --check . && python -m pytest tests/ -v
```

All tests are self-contained with fixture data. No tests depend on external files.
