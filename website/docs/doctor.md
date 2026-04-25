---
sidebar_position: 4
title: Doctor Command
---

# Doctor Command

Reference for `copilot-setup doctor`.

## Usage

```bash
copilot-setup doctor
```

## What it does

Probes every MCP server defined in `~/.copilot/mcp-config.json` and reports health status.

## Probe types

**stdio servers**: Launches the server process, sends a JSON-RPC `initialize` request with proper Content-Length framing (`Content-Length: N\r\n\r\n{json}`), waits for response with timeout.

**HTTP servers**: Sends an HTTP POST to the server URL with the initialize payload, checks response.

## Status codes

| Status | Meaning |
|--------|---------|
| `ok` | Server responded successfully to initialize |
| `timeout` | Server didn't respond within the timeout period |
| `needs_oauth` | HTTP server returned 401 with WWW-Authenticate header |
| `error` | Server process failed to start or returned an error |
| `not_found` | Server command/binary not found on PATH |

## Output format

Each server gets a line with its name, transport type, and status. Color-coded: green for ok, yellow for needs_oauth, red for errors.

## Tips

- Run doctor after adding new MCP servers to verify they work
- `needs_oauth` status means the HTTP server requires OAuth — see [Troubleshooting](troubleshooting.md) for workarounds
- Doctor reads the same `mcp-config.json` that the TUI uses
