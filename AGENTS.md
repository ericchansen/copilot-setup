# AGENTS.md — copilot-setup

## Repository Purpose

A **Textual TUI dashboard** for viewing and managing GitHub Copilot CLI configuration.
It reads `~/.copilot/` configuration from disk and presents it in a navigable,
filterable, tabbed interface. Some tabs support actions (plugin toggle/remove/upgrade,
MCP server removal) via CLI delegation or direct config writes.

## Architecture

- **Entry point**: `app.py` → `main()` → `CopilotSetupApp`
- **Data layer**: `data/*.py` — one `ReadProvider` per tab (frozen dataclass + `load()`)
- **Tab layer**: `tabs/*.py` — one `BaseTab` subclass per tab (columns, rows, detail, filter)
- **Widgets**: `widgets/` — reusable UI components (footer, status bar, detail pane, filter)
- **Doctor**: `doctor.py` — MCP server health probes (stdio + HTTP), CLI subcommand

### BaseTab / Provider Protocol

Every tab follows the same pattern:
1. A **data provider** in `data/` defines a frozen `@dataclass` and a `load()` function
2. A **tab class** in `tabs/` extends `BaseTab[T]` and implements:
   - `columns` — list of column definitions
   - `key_for(item)` — unique key for each row
   - `row_for(item)` — tuple of cell values
   - `detail_for(item)` — Rich markup for the detail pane
   - `filter_text(item)` — searchable text for filtering

### Tab Registration

All 11 tabs are registered in `app.py`'s `_TAB_DEFINITIONS` list. Each entry is a
`(label, TabClass)` tuple. Tab order follows this list.

## Key Design Decisions

- **Minimal writes**: Plugin toggle edits `config.json` directly; remove/upgrade delegate to `copilot` CLI. Most tabs are read-only viewers
- **Provider protocol**: `ReadProvider` has `load() -> list[T]`; `WriteProvider` adds `save()`
- **Frozen dataclasses**: All data items are immutable — no in-place mutation
- **Load generation tokens**: `_load_gen = itertools.count()` prevents stale async results
- **Plugin-bundled discovery**: Skills and Agents scan `installed-plugins/*/skills|agents/` too
- **Tab bar disabled**: `tabs.can_focus = False` in `on_ready()` so arrow keys control content
- **Rich markup escaping**: `[a]` in footer must be escaped as `\[a]` to avoid Rich tag parsing

## File Conventions

When editing:
- `app.py` — TUI app class, tab registry, global key bindings, doctor subcommand hook
- `config.py` — Path functions only (no constants). Functions for testability via env var override
- `data/*.py` — Pure data loading. Each returns `list[FrozenDataclass]`. No Textual imports
- `tabs/*.py` — UI layer. Each extends `BaseTab[T]`, never loads data directly
- `widgets/*.py` — Reusable Textual widgets. No data-loading logic
- `doctor.py` — Self-contained. Reads mcp-config.json via `config.mcp_config_json()`
- `platform_ops.py` — Read-only platform utilities (link detection, LSP validation)

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
