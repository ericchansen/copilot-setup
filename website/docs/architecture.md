---
sidebar_position: 6
title: Architecture
---

### Overview

copilot-setup follows a strict separation between data loading and UI rendering.

```
┌─────────────┐    ┌──────────────┐    ┌───────────┐
│ config files │───▶│ data/*.py    │───▶│ tabs/*.py  │
│ (~/.copilot/)│    │ (providers)  │    │ (UI layer) │
└─────────────┘    └──────────────┘    └───────────┘
```

### Data Layer (`data/`)

Each tab has a corresponding **data provider** in `data/`:

- Defines a **frozen dataclass** representing one item (e.g., `PluginItem`, `McpServerItem`)
- Implements a `load()` function that reads from disk and returns `list[T]`
- Providers are pure Python — no Textual imports, no UI logic
- All dataclasses are frozen (immutable) — no in-place mutation

Two protocols:
- `ReadProvider` — `load() -> list[T]` (most tabs)
- `WriteProvider` — adds `save()` for tabs with mutation actions

### Tab Layer (`tabs/`)

Each tab extends `BaseTab[T]` and implements:

| Method | Purpose |
|--------|---------|
| `columns` | Column definitions (name, width) |
| `key_for(item)` | Unique key for each row |
| `row_for(item)` | Tuple of cell values for display |
| `detail_for(item)` | Rich markup for the detail pane |
| `filter_text(item)` | Searchable text for filtering |

BaseTab handles:
- Threaded data loading (never blocks the UI)
- Load generation tokens to prevent stale async results
- Automatic detail pane sync on row selection
- Filter integration with FilterInput widget

### Tab Registration

All 11 tabs are registered in `app.py`'s `_TAB_DEFINITIONS` list:

```python
_TAB_DEFINITIONS = [
    ("Plugins", PluginsTab),
    ("MCP Servers", McpServersTab),
    # ... 9 more
]
```

Adding a new tab requires only:
1. Create `data/new_thing.py` with a frozen dataclass and `load()` function
2. Create `tabs/new_thing.py` extending `BaseTab[NewThing]`
3. Add a tuple to `_TAB_DEFINITIONS`

### Widgets (`widgets/`)

Reusable UI components:
- **DetailPane** — right panel showing Rich markup for the selected row
- **FilterInput** — text input for searching (matches all columns, not just name)
- **FooterBar** — bottom bar showing available action keys for the current tab
- **StatusBar** — top bar with item count and active filter state
- **StatusRender** — Rich markup helpers for status/reason cells (color-coded)

### Utilities

- `utils/cli.py` — `run_copilot()` subprocess wrapper for CLI passthrough
- `utils/file_io.py` — `read_json()` / `read_text()` helpers
- `config.py` — Path functions (`copilot_home()`, `mcp_config_json()`, etc.) with env var override for testing
- `platform_ops.py` — Cross-platform link detection (Windows junctions), LSP binary validation
- `doctor.py` — MCP server health probes (stdio + HTTP)

### Contributing

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run all checks (must pass before committing)
python -m ruff check .           # lint
python -m ruff format --check .  # format
python -m pytest tests/ -v       # test
```

Tests are self-contained with fixture data — no tests depend on your local `~/.copilot/` state.
