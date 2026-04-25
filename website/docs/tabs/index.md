---
sidebar_position: 2
title: Tab Reference
---

# Tab Reference

copilot-setup organizes your Copilot CLI configuration into **11 tabs**, each focused on a specific area. Every tab displays a **data table** on the left and a **detail pane** on the right — select any row to see its full details.

Press `/` in any tab to open the **filter bar** and narrow results by keyword.

## Tab Overview

| Tab | What it shows | Key actions |
|-----|---------------|-------------|
| [Plugins](plugins.md) | Installed Copilot CLI plugins | `a` add, `x` remove, `t` toggle, `u` upgrade, `m` marketplace |
| [MCP Servers](mcp-servers.md) | MCP server definitions | `a` add, `x` remove |
| [Skills & Agents](skills-agents.md) | Skill and Agent YAML files (user + plugin-bundled) | — |
| [LSP Servers](other-tabs.md#lsp-servers) | Language servers from `lsp-config.json` | — |
| [Extensions](other-tabs.md#extensions) | VS Code extensions | — |
| [Hooks](other-tabs.md#hooks) | Git hooks from `config.json` | — |
| [Permissions](other-tabs.md#permissions) | Trusted folders, allowed/denied URLs | — |
| [Profiles](other-tabs.md#profiles) | User profiles | — |
| [Environment](other-tabs.md#environment) | Copilot-related environment info | — |
| [Settings](other-tabs.md#settings) | `config.json` settings | `e` edit |

## Navigation

- **Tab bar** — Click a tab label or use number keys `1`–`9`, `0`, `-` to jump directly.
- **Arrow keys** — Move between rows in the data table.
- **Enter** — Expand the detail pane for the selected row.
- **`/`** — Open the filter bar (works in every tab).
- **`q`** — Quit the application.

Tabs with write actions (Plugins, MCP Servers, Settings) are covered in detail on their own pages. The remaining tabs are view-only and are summarized in [Other Tabs](other-tabs.md).
