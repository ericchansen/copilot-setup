# MCP OAuth and Copilot CLI plugins

## Summary

GitHub Copilot CLI auto-triggers an OAuth 2.1 flow for **user-level** HTTP MCP
servers (registered in `~/.copilot/mcp-config.json`, typically via
`copilot mcp add --transport http ...`) but does **not** auto-trigger OAuth for
HTTP MCP servers declared inside a plugin's `.mcp.json`. The plugin-level server
loads, returns `401` on first use, and silently fails with no prompt.

This is a known gap in Copilot CLI as of the time of writing. This document
captures the diagnosis and two workarounds.

## Diagnosis

The signature is:

1. Plugin installs fine (`copilot plugin list` shows it).
2. `/mcp` lists the plugin's HTTP server but it never becomes available.
3. Direct probe returns `401` with
   `WWW-Authenticate: Bearer, resource_metadata=...`.
4. Fetching the resource-metadata URL returns the expected AAD/IdP metadata.

Example that bit us in this repo: `powerbi-remote` from the `msx-mcp` plugin,
pointing at `https://api.fabric.microsoft.com/v1/mcp/powerbi`. AAD tenant
`login.microsoftonline.com/common/v2.0`, scope
`https://analysis.windows.net/powerbi/api/.default`.

Quick probe from PowerShell:

```powershell
try { Invoke-WebRequest -Uri "<URL>" -Method POST -Body '{}' -ContentType 'application/json' -UseBasicParsing }
catch { $_.Exception.Response.Headers['WWW-Authenticate'] }
```

If you see `Bearer, resource_metadata=...` — this gap is what you're hitting.

## Workaround A — add a duplicate user-level entry (recommended)

Register the same HTTP MCP server at **user** level so the CLI handles OAuth:

```bash
copilot mcp add --transport http <name> <url>
```

The CLI will prompt for OAuth on first use and cache tokens at user scope. The
plugin-level entry still exists but is effectively shadowed; tools resolve
through the user-level server.

Trade-offs:

- Requires running `copilot mcp add` per affected plugin server — `copilot-setup`
  does not currently automate this.
- Users see the server name twice in `/mcp` output.
- Works today, no extra moving parts.

## Workaround B — run an aggregator in front

Tools like [1MCP](https://github.com/1mcp-app/agent) aggregate N MCP servers
behind a single endpoint with OAuth 2.1 support. You register **one** stdio/HTTP
server (the aggregator) with Copilot CLI, and the aggregator handles auth and
fan-out to the plugin-declared servers.

Trade-offs:

- Extra process to run and keep alive.
- OAuth is now managed by the aggregator, not Copilot CLI.
- Solves the gap for any number of affected servers at once.
- Good fit if you're hitting this on three or more plugin-level HTTP MCPs.

Out of scope for `copilot-setup` to ship; documented here for awareness.

## Why we don't fix this in `copilot-setup`

The root cause is in the Copilot CLI's MCP client, not in our merge engine.
Papering over it with a forced OAuth flow inside `copilot-setup` would:

1. Re-implement OAuth 2.1 in a place where it doesn't belong.
2. Duplicate state that the CLI already manages for user-level servers.
3. Break quietly if the CLI's OAuth behavior ever changes.

What `copilot-setup` will do instead:

- **Detect the condition.** The forthcoming `doctor` step probes HTTP MCPs and
  surfaces `needs_oauth` when it sees `401 + WWW-Authenticate: Bearer`.
- **Surface it in the TUI.** The Servers tab will show `OAuth: needs auth`
  inline so the user knows to apply Workaround A.

## References

- [About CLI plugins][doc-about] (GitHub docs)
- [Copilot CLI plugin reference][doc-ref]
- [1MCP Agent](https://github.com/1mcp-app/agent) — aggregator with OAuth 2.1

[doc-about]: https://docs.github.com/en/copilot/concepts/agents/copilot-cli/about-cli-plugins
[doc-ref]: https://docs.github.com/en/copilot/reference/cli-plugin-reference
