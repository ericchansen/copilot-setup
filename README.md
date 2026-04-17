# copilot-setup

A Textual TUI dashboard for GitHub Copilot CLI configuration. Discovers, merges, and
deploys configuration from multiple sources — and shows you exactly what's configured.

## What It Does

`copilot-setup` launches an interactive terminal dashboard that:

- **Shows config state** — sources, MCP servers, skills, plugins, and LSP servers
- **Detects drift** — compares desired state (from sources) against actual deployed state
- **Runs actions** — setup via `F5` key binding
- **Multi-source merging** — additive for servers/skills/plugins, first-wins for instructions

## Multi-Source Architecture

The engine itself contains **no configuration data**. All data comes from config sources — directories on disk containing JSON files and skills.

### Config Sources

Register sources in `~/.copilot/config-sources.json`:

```json
[
  {"name": "personal", "path": "~/repos/copilot-config"},
  {"name": "work",     "path": "~/repos/copilot-config-work"}
]
```

Each source is a directory containing any combination of:

| File | Purpose | Merge Strategy |
|------|---------|----------------|
| `mcp.json` | MCP server definitions | **Additive** — merged across all sources |
| `plugins.json` | Copilot CLI plugin definitions | **Additive** — merged across all sources |
| `lsp-servers.json` | LSP server definitions | **First-wins** — first source providing it |
| `config.portable.json` | Portable settings | **First-wins** |
| `copilot-instructions.md` | Global instructions | **First-wins** |
| `skills/` | Directory of skills (each with SKILL.md) | **Additive** — all skills linked |

## Installation

```bash
pip install -e ~/repos/copilot-setup
```

## Usage

```bash
# Launch the TUI dashboard
copilot-setup

# Check config-source repos for upstream updates
copilot-setup update

# Fast-forward pull any sources that are behind
copilot-setup update --apply

# Probe MCP servers live (spawn/HTTP initialize); shows ok / timeout /
# needs_oauth / etc. per server.
copilot-setup doctor
```

### Key Bindings

| Key | Action |
|-----|--------|
| `F5` | Run setup (discover, merge, deploy) |
| `R` | Refresh dashboard state |
| `T` | Enable / disable plugin (Plugins tab) |
| `U` | Upgrade plugin (Plugins tab) |
| `X` | Uninstall plugin (Plugins tab) |
| `Q` | Quit |

The dashboard has 5 tabs: **Sources**, **MCP Servers**, **Skills**, **Plugins**, **LSP**.

## Known issues and gotchas

- [MCP OAuth and Copilot CLI plugins](docs/mcp-oauth-and-plugins.md) — HTTP MCPs
  declared inside a plugin do not auto-trigger Copilot CLI's OAuth flow. Covers
  the diagnosis and two workarounds.

## Development

```bash
# Install in editable mode
pip install -e .

# Lint
python -m ruff check .

# Format check
python -m ruff format --check .

# Test
python -m pytest tests/ -v

# All three (must pass before committing)
python -m ruff check . && python -m ruff format --check . && python -m pytest tests/ -v
```

## Project Structure

```
src/copilotsetup/
  app.py                ← TUI entry point (Textual App, tabbed dashboard)
  app.tcss              ← Textual CSS stylesheet
  state.py              ← Desired + actual state computation (data layer)
  screens/
    action_screen.py    ← Action execution screen (setup)
  widgets/
    source_table.py     ← Sources tab population
    server_table.py     ← MCP Servers tab population
    skill_table.py      ← Skills tab population
    plugin_table.py     ← Plugins tab population
    lsp_table.py        ← LSP tab population
  models.py             ← SetupContext, StepResult, Summary, UIProtocol
  runner.py             ← Step protocol + pipeline runner (used by actions)
  ui.py                 ← Terminal UI rendering (used internally by runner)
  sources.py            ← Config source discovery & merging
  config.py             ← MCP/LSP config generation
  skills.py             ← Skill discovery, linking, plugin management
  platform_ops.py       ← Cross-platform symlinks, junctions
  git_helpers.py        ← Git authentication detection
  optional_deps.py      ← Interactive optional dependency installs
  build_detect.py       ← Build system detection for MCP servers
  init.py               ← Onboarding wizard (copilot-setup init)
  steps/                ← 15 individual setup steps
```
