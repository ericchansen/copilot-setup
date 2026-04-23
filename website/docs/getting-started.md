---
sidebar_position: 1
title: Getting Started
---

# Getting Started

**copilot-setup** is a read-only terminal dashboard for inspecting your GitHub Copilot CLI configuration. It reads `~/.copilot/` and presents everything in a navigable, filterable TUI — without ever modifying your files.

## Prerequisites

- **Python 3.11+**
- **GitHub Copilot CLI** installed and configured — the `~/.copilot/` directory must exist with at least a `config.json`

## Installation

Install from PyPI:

```bash
pip install copilot-setup
```

Or install from source for development:

```bash
git clone https://github.com/ericchansen/copilot-setup.git
cd copilot-setup
pip install -e .
```

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

## Read-Only by Design

:::info
**copilot-setup never writes to any configuration file.** It is a pure viewer. Any actions that modify config — such as toggling a plugin or adding an MCP server — delegate to the `copilot` CLI commands rather than writing files directly.
:::
