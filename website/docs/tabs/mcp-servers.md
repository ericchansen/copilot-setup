---
sidebar_position: 2
title: MCP Servers
---

# MCP Servers Tab

The MCP Servers tab displays all configured Model Context Protocol servers that extend Copilot CLI with external tools.

## Columns

| Column | Description |
|--------|-------------|
| **Name** | Server identifier |
| **Transport** | `stdio` or `http` |
| **Status** | Connection state |
| **Command / URL** | Executable command (stdio) or endpoint URL (http) |

## Detail Pane

Selecting a server shows its full configuration:

- **Name** and **transport type**
- **Command** and **args** (for stdio servers)
- **URL** (for HTTP servers)
- **Environment variables** passed to the server process

## Actions

| Key | Action | Description |
|-----|--------|-------------|
| `a` | **Add** | Add a new MCP server definition. |
| `x` | **Remove** | Remove the selected server from configuration. |

## How It Works

Server definitions are read from `~/.copilot/mcp-config.json`. Each entry specifies:

- A **name** used as the server identifier
- A **transport type** — either `stdio` (launches a local process) or `http` (connects to a remote endpoint)
- For stdio: the **command** to run and its **args**
- For HTTP: the **URL** to connect to
- Optional **environment variables** injected into the server's process

## Health Probing with `copilot-setup doctor`

The [`copilot-setup doctor`](/docs/doctor) command probes each configured server to verify connectivity:

- **stdio servers** — Launches the command and sends an MCP `initialize` request, then waits for a valid response.
- **HTTP servers** — Sends an HTTP POST to the server's URL with an `initialize` payload.

Servers that respond correctly are marked healthy; failures are reported with error details.

## OAuth Note

:::caution
HTTP servers declared inside plugins may not automatically trigger OAuth authentication flows. If a plugin-bundled HTTP server requires OAuth and you see authentication errors, refer to the [Troubleshooting](../troubleshooting.md) page for workarounds.
:::
