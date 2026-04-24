---
sidebar_position: 3
title: Key Bindings
---

# Key Bindings

Complete keyboard reference for copilot-setup.

## Global Keys

| Key | Action |
|-----|--------|
| `←` / `→` | Switch between tabs |
| `↑` / `↓` | Navigate rows in the current tab |
| `/` | Open filter — type to search across all columns |
| `Escape` | Clear active filter |
| `r` | Refresh data from disk |
| `?` | Show help overlay with all key bindings |
| `q` | Quit copilot-setup |

## Plugins Tab

| Key | Action |
|-----|--------|
| `a` | Install a new plugin (prompts for GitHub slug like `owner/repo`) |
| `x` | Uninstall selected plugin (shows confirmation) |
| `t` | Toggle selected plugin enabled/disabled |
| `u` | Upgrade selected plugin (if newer version available) |
| `m` | Open marketplace browser to discover plugins |

## MCP Servers Tab

| Key | Action |
|-----|--------|
| `a` | Add a new MCP server |
| `x` | Remove selected MCP server (shows confirmation) |

## Settings Tab

| Key | Action |
|-----|--------|
| `e` | Edit selected setting (toggles booleans, cycles enums, text input for strings) |

## How Actions Work

Most mutation actions (remove, upgrade) delegate to the `copilot` CLI — copilot-setup calls `copilot plugin uninstall`, `copilot plugin update`, `copilot mcp remove`, etc. and then refreshes the display. The exception is **plugin toggle**, which edits `config.json` directly.

This means:

- Most actions require `copilot` CLI to be installed and on PATH
- Changes are immediately reflected in the TUI after the action completes
- If a CLI command fails, an error toast appears with the failure details

## Filter Behavior

When a filter is active:

- Only rows matching the filter text are shown
- Filter matches across all columns (not just the name column)
- The status bar shows the filter text and match count
- Press `Escape` to clear the filter and show all rows
