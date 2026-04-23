---
sidebar_position: 5
title: Troubleshooting
---

### MCP OAuth and Plugin HTTP Servers

GitHub Copilot CLI auto-triggers an OAuth 2.1 flow for **user-level** HTTP MCP servers (registered in `~/.copilot/mcp-config.json` via `copilot mcp add --transport http ...`) but does **not** auto-trigger OAuth for HTTP MCP servers declared inside a plugin's `.mcp.json`. The plugin-level server loads, returns 401 on first use, and silently fails.

#### Symptoms
1. Plugin installs fine (`copilot plugin list` shows it)
2. `/mcp` lists the plugin's HTTP server but it never becomes available
3. `copilot-setup doctor` shows `needs_oauth` for the server
4. Direct HTTP probe returns `401` with `WWW-Authenticate: Bearer, resource_metadata=...`

#### Workaround A — Duplicate user-level entry (recommended)
Register the same HTTP MCP server at user level:
```bash
copilot mcp add --transport http <name> <url>
```
The CLI will prompt for OAuth on first use. The plugin-level entry is effectively shadowed.

#### Workaround B — Use an aggregator
Tools like [1MCP](https://github.com/1mcp-app/agent) aggregate multiple MCP servers behind a single endpoint with OAuth 2.1 support.

### Common Issues

#### "copilot-setup: command not found"
Make sure the package is installed and the Python scripts directory is on your PATH:
```bash
pip install copilot-setup
# If installed but not found, check:
python -m copilotsetup
```

#### Empty tabs / No data showing
- Verify `~/.copilot/` exists and contains `config.json`
- Make sure Copilot CLI has been configured at least once
- Try pressing `r` to refresh data from disk

#### Actions not working
- Actions require the `copilot` CLI to be on PATH
- Check that `copilot --version` works in your terminal
- Error details appear as toast notifications in the TUI

#### Doctor shows all timeouts
- Check that MCP server binaries exist at the configured paths
- For stdio servers, the command must be executable
- For HTTP servers, ensure the URLs are reachable
