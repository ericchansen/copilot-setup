# copilot-setup

A read-only Textual TUI dashboard for GitHub Copilot CLI. Shows you exactly what's
configured — MCP servers, plugins, skills, agents, settings, and more — without
modifying anything.

![copilot-setup dashboard](docs/screenshot.png)

## What It Does

`copilot-setup` reads Copilot CLI's on-disk configuration (`~/.copilot/`) and presents
it in a navigable, filterable, tabbed dashboard. It's a pure viewer — any Copilot CLI
user can install it and immediately see what's configured.

- **11 tabs** — Plugins, MCP Servers, Skills, Agents, LSP Servers, Extensions,
  Hooks, Permissions, Profiles, Environment, Settings
- **Plugin management** — toggle enable/disable, detect upgrades, install/remove
- **Filter** — press `/` to search across any tab
- **Detail pane** — highlight a row to see full details
- **Doctor** — `copilot-setup doctor` probes each MCP server (stdio + HTTP) and reports health

## Installation

```bash
pip install -e ~/repos/copilot-setup
```

Requires Python ≥ 3.11 and [Textual](https://textual.textualize.io/) ≥ 1.0.

## Usage

```bash
# Launch the TUI dashboard
copilot-setup

# Probe MCP servers for health (ok / timeout / needs_oauth / etc.)
copilot-setup doctor
```

### Key Bindings

| Key | Action |
|-----|--------|
| `←` / `→` | Switch tabs |
| `↑` / `↓` | Navigate rows |
| `/` | Filter current tab |
| `Escape` | Clear filter |
| `r` | Refresh data from disk |
| `?` | Help overlay |
| `q` | Quit |

**Plugins tab:** `a` add, `x` remove, `t` toggle, `u` upgrade, `m` marketplace
**MCP Servers tab:** `a` add, `x` remove

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
  app.py                ← TUI entry point (CopilotSetupApp, 11-tab dashboard)
  app.tcss              ← Textual CSS stylesheet
  config.py             ← Path functions (copilot_home, mcp_config_json, etc.)
  doctor.py             ← MCP server health probes (stdio + HTTP)
  platform_ops.py       ← Cross-platform link detection, LSP binary validation
  data/
    base.py             ← ReadProvider / WriteProvider protocols
    environment.py      ← Environment tab data (Copilot home, paths, versions)
    mcp_servers.py      ← MCP server entries from mcp-config.json
    plugins.py          ← Installed/enabled plugins from config.json
    skills.py           ← Skills from ~/.copilot/skills/ + plugin-bundled
    agents.py           ← Agents from ~/.copilot/agents/ + plugin-bundled
    settings.py         ← Config.json settings (non-structural keys)
    hooks.py            ← Git hooks from config.json
    permissions.py      ← Trusted folders, allowed/denied URLs
    profiles.py         ← Copilot profiles with active detection
    extensions.py       ← VS Code extensions from ~/.copilot/extensions/
    lsp_servers.py      ← LSP servers from lsp-config.json
  tabs/
    base.py             ← BaseTab abstract class (item-based, filterable)
    environment.py … lsp_servers.py  ← One tab class per data provider
  screens/
    help_screen.py      ← Modal help overlay (? key)
  widgets/
    footer_bar.py       ← Bottom bar with action key indicators
    status_bar.py       ← Top bar with item count + filter state
    detail_pane.py      ← Right panel showing selected item details
    filter_input.py     ← Filter text input widget
    status_render.py    ← Rich markup helpers for status/reason cells
  utils/
    file_io.py          ← read_json / read_text helpers
    cli.py              ← run_copilot() subprocess wrapper
```
