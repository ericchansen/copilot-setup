# AGENTS.md — copilot-setup

## Repository Purpose

This is the **configuration engine** for GitHub Copilot CLI. It discovers, merges, and
deploys configuration from multiple sources. The engine contains NO configuration data —
all data (servers, plugins, skills, instructions) comes from config source repos.

## Architecture

- **Entry point**: `setup.py` → `main()` → `_run_setup()`
- **Source discovery**: `lib/sources.py` reads `~/.copilot/config-sources.json`
- **Pipeline**: 16 ordered steps defined in `copilot_setup/steps/__init__.py`
- **Step protocol**: Each step has `name: str`, `check(ctx) -> bool`, `run(ctx) -> StepResult`

## Key Design Decisions

- **Engine/data separation**: No `mcp-servers.json`, no skills, no instructions in this repo
- **Additive merging**: MCP servers, plugins, and skills are collected from ALL sources
- **First-wins merging**: Instructions, portable config, and LSP config take the first source
- **Server deduplication**: By name — first occurrence wins
- **Category field stripped**: `load_source()` removes `category` from server definitions
- **Legacy support**: Sources using `.copilot/` subdir layout are auto-detected

## File Conventions

When editing:
- `lib/sources.py` — Core merging logic. If you change merge strategies, update tests
- `copilot_setup/steps/` — Each step reads from `ctx` (SetupContext). Steps must not import
  data directly; they get it from the context which is populated from merged sources
- `setup.py` — Builds SetupContext by calling `discover_sources()` → `load_source()` → `merge_sources()`

## Testing

```bash
python -m pytest tests/ -v
python -m ruff check .
```

All tests are self-contained with fixture data. No tests depend on external files.
