---
sidebar_position: 1
title: Plugins
---

# Plugins Tab

The Plugins tab shows all installed Copilot CLI plugins, their status, and available upgrades.

## Columns

| Column | Description |
|--------|-------------|
| **Name** | Plugin name (GitHub slug) |
| **Version** | Currently installed version |
| **Status** | `enabled` or `disabled` |
| **Upgrade Available** | Latest version if newer than installed, otherwise blank |

## Detail Pane

Selecting a plugin reveals its full details:

- **Name** and **version**
- **Path** on disk (`~/.copilot/installed-plugins/<name>/`)
- **Enabled** state
- **Cache path**
- **Upgrade info** — latest available version and whether an upgrade is pending

## Actions

| Key | Action | Description |
|-----|--------|-------------|
| `a` | **Add** | Install a new plugin. Prompts for a GitHub slug (e.g., `owner/repo`). |
| `x` | **Uninstall** | Remove the selected plugin. Shows a confirmation prompt before deleting. |
| `t` | **Toggle** | Enable or disable the selected plugin without uninstalling it. |
| `u` | **Upgrade** | Upgrade the selected plugin to the latest version (only available when an upgrade is detected). |
| `m` | **Marketplace** | Open the plugin marketplace browser to discover new plugins. |

## How It Works

Plugin data is read from the `installedPlugins` section of `~/.copilot/config.json`. Each entry records the plugin's GitHub slug, installed version, enabled state, and local path.

**Upgrade detection** compares the installed version against the latest git tags in the plugin's GitHub repository. If a newer tag exists, the "Upgrade Available" column shows the new version.

## Plugin-Bundled Content

Plugins can bundle their own **skills** and **agents** by placing YAML files in their installation directory:

- `~/.copilot/installed-plugins/<plugin>/skills/` — bundled skills
- `~/.copilot/installed-plugins/<plugin>/agents/` — bundled agents

These bundled items appear in the [Skills & Agents](./skills-agents) tab, attributed to their parent plugin. See the Skills & Agents page for details on how discovery works.
