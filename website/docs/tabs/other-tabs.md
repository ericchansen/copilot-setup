---
sidebar_position: 4
title: Other Tabs
---

# Other Tabs

These six tabs are read-only viewers with no write actions. Each follows the standard layout — data table on the left, detail pane on the right, `/` to filter.

## LSP Servers

Shows language servers configured in `~/.copilot/lsp-config.json`. copilot-setup validates that each server's binary path exists on disk and flags missing executables.

| Column | Description |
|--------|-------------|
| **Name** | Language server identifier |
| **Language** | Language or file type served |
| **Command** | Binary path and arguments |
| **Status** | Whether the binary exists on disk |

## Extensions

Displays VS Code extensions registered under `~/.copilot/extensions/`. These extensions integrate with Copilot CLI's editing capabilities.

| Column | Description |
|--------|-------------|
| **Name** | Extension display name |
| **Version** | Installed version |

## Hooks

Lists git hooks defined in the `hooks` section of `~/.copilot/config.json`. Hooks run automatically at specific points in the Copilot CLI lifecycle.

| Column | Description |
|--------|-------------|
| **Event** | Hook trigger point (e.g., `pre-commit`, `post-push`) |
| **Command** | Shell command to execute |
| **Type** | Hook type |

## Permissions

Displays three permission lists read from `~/.copilot/config.json`:

- **Trusted Folders** — Directories where Copilot CLI is allowed to operate without confirmation prompts.
- **Allowed URLs** — Network endpoints that tools and MCP servers are permitted to access.
- **Denied URLs** — Network endpoints that are explicitly blocked.

Each section is displayed as a separate group within the tab.

## Profiles

Shows user profiles from `~/.copilot/profiles/`. Profiles let you maintain separate configurations for different workflows or projects. The currently active profile is highlighted in the data table.

| Column | Description |
|--------|-------------|
| **Name** | Profile name |
| **Active** | Whether this profile is currently selected |

## Environment

Displays Copilot-related environment information and system paths. This tab is useful for debugging configuration issues and verifying your setup.

Key items shown:

- **Copilot home directory** (`~/.copilot/`)
- **Config file locations** — paths to `config.json`, `mcp-config.json`, `lsp-config.json`
- **Python version** — detected Python interpreter
- **Node.js version** — detected Node.js runtime
- **Environment variables** — any `COPILOT_*` variables currently set

## Settings

Displays non-structural keys from `~/.copilot/config.json` — the individual configuration values rather than complex objects like `installedPlugins` or `hooks`.

| Column | Description |
|--------|-------------|
| **Key** | Setting name |
| **Value** | Current value |
| **Type** | Data type (boolean, string, enum) |

### Edit Action

Press `e` to edit the selected setting. The input method depends on the setting's type:

- **Boolean** — Toggles between `true` and `false`
- **Enum** — Cycles through the allowed values
- **String** — Opens a text input prompt

Settings changes are applied via `copilot config set` CLI passthrough, ensuring they are validated and persisted correctly.
