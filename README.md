# copilot-setup

The configuration engine for GitHub Copilot CLI. Discovers, merges, and deploys configuration from multiple sources.

## What It Does

`copilot-setup` is a Python package that manages your Copilot CLI environment:

- **Skills** — links skill directories into `~/.copilot/skills/`
- **MCP servers** — builds and generates `mcp-config.json`
- **LSP servers** — validates binaries and generates `lsp-config.json`
- **Plugins** — installs Copilot CLI plugins and creates shell aliases
- **Config files** — symlinks instructions, patches `config.json`

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
# Interactive setup (discovers sources, merges, deploys)
copilot-setup

# Non-interactive
copilot-setup --non-interactive

# Remove skills not managed by any source
copilot-setup --clean-orphans

# Backup personalization files
copilot-setup backup

# Restore from backup
copilot-setup restore

# Adopt untracked skills
copilot-setup sync-skills
```

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
  cli.py                ← CLI entry point (copilot-setup command)
  models.py             ← SetupContext, StepResult, Summary, UIProtocol
  runner.py             ← Step protocol + pipeline runner
  ui.py                 ← Terminal UI rendering
  sources.py            ← Config source discovery & merging
  config.py             ← MCP/LSP config generation
  skills.py             ← Skill discovery, linking, plugin management
  platform_ops.py       ← Cross-platform symlinks, junctions
  backup.py             ← Backup & OneDrive sync
  restore.py            ← Restore from backup
  git_helpers.py        ← Git authentication detection
  optional_deps.py      ← Interactive optional dependency installs
  build_detect.py       ← Build system detection for MCP servers
  init.py               ← Onboarding wizard (copilot-setup init)
  steps/                ← 15 individual setup steps
```
