---
sidebar_position: 1
title: Getting Started
---

# Getting Started

**copilot-setup** is a terminal dashboard for viewing and managing your GitHub Copilot CLI configuration. It reads `~/.copilot/` and presents everything in a navigable, filterable TUI. Some tabs support direct actions — toggle, upgrade, and remove plugins or MCP servers without leaving the dashboard.

## Prerequisites

- **Python 3.11+**
- **GitHub Copilot CLI** installed and configured — the `~/.copilot/` directory must exist with at least a `config.json`

## Installation

Install as an isolated CLI tool with [uv](https://docs.astral.sh/uv/) (recommended):

```bash
uv tool install copilot-setup
```

Or run directly without installing:

```bash
uvx copilot-setup
```

Or install from source for development:

```bash
git clone https://github.com/ericchansen/copilot-setup.git
cd copilot-setup
uv tool install -e .           # editable install
uv tool install ruff pytest    # dev tools (for linting/testing)
```

:::tip Why uv over pip?
Global `pip install` pollutes your system Python and causes version conflicts. `uv tool install` gives each tool its own isolated venv — faster than pipx, no conflicts. If you previously used `pip install copilot-setup`, clean up with `pip uninstall copilot-setup` first.
:::

## First Launch

```bash
copilot-setup
```

A tabbed dashboard opens directly in your terminal:

- **11 tabs** across the top: Plugins, MCP Servers, Skills, Agents, LSP Servers, Extensions, Hooks, Permissions, Profiles, Environment, Settings
- **Left/Right arrows** switch between tabs
- **Up/Down arrows** navigate rows within a tab
- A **detail pane** on the right shows full information for the selected item
- Press **`/`** to filter the current tab
- Press **`?`** for help
- Press **`q`** to quit

:::tip
Arrow keys control content navigation, not the tab bar. Left/Right switch tabs; Up/Down scroll rows.
:::

## Doctor Command

The `doctor` subcommand probes each configured MCP server and reports its health status:

```bash
copilot-setup doctor
```

This checks both **stdio** and **HTTP** transport servers defined in your `mcp-config.json` and reports which ones are reachable.

## What copilot-setup Reads

copilot-setup discovers your configuration from these paths under `~/.copilot/`:

| Path | Content |
|------|---------|
| `config.json` | Plugins, settings, hooks, permissions |
| `mcp-config.json` | MCP server definitions |
| `skills/` | Skill YAML files |
| `agents/` | Agent YAML files |
| `profiles/` | User profiles |
| `extensions/` | VS Code extension metadata |
| `lsp-config.json` | LSP server definitions |
| `installed-plugins/*/` | Plugin-bundled skills, agents, and other content |

## How Actions Work

:::info
**Most tabs are view-only** — they display your config files without modification. Two tabs support actions today:

- **Plugins** — toggle (directly edits `config.json`), remove, and upgrade (delegate to `copilot` CLI)
- **MCP Servers** — remove (delegates to `copilot` CLI)

The **Settings** tab has a placeholder `e` key binding for editing, but this is not yet implemented.

All CLI-delegated actions run the official `copilot` command as a subprocess. Plugin toggle is the only action that writes to `config.json` directly.
:::
