"""Step: Generate mcp-config.json."""

from __future__ import annotations

from copilotsetup.config import generate_mcp_config
from copilotsetup.models import SetupContext, StepResult


class McpConfigStep:
    """Generate ``~/.copilot/mcp-config.json`` from enabled servers."""

    name = "MCP · Config"

    def check(self, ctx: SetupContext) -> bool:
        return True

    def run(self, ctx: SetupContext) -> StepResult:
        result = StepResult()
        mcp_config_path = ctx.copilot_home / "mcp-config.json"

        # Exclude plugin-managed servers — their plugin .mcp.json provides the config
        config_servers = {
            name: entry for name, entry in ctx.enabled_servers.items() if name not in ctx.plugin_managed_names
        }

        # Show per-source server attribution (first-wins, excluding plugin-managed)
        merged = getattr(ctx, "merged_config", None)
        if merged:
            seen_servers: set[str] = set()
            plugin_managed = set(getattr(ctx, "plugin_managed_names", set()))
            for source in getattr(merged, "sources", []):
                source_servers = getattr(source, "servers", None)
                if not source_servers:
                    continue
                contributing = []
                for name in source_servers:
                    if name in plugin_managed or name in seen_servers:
                        continue
                    contributing.append(name)
                    seen_servers.add(name)
                if contributing:
                    names = ", ".join(sorted(contributing))
                    result.item(f"[{source.name}]", "info", f"servers: {names}")

        info = generate_mcp_config(config_servers, ctx.mcp_paths, ctx.external_dir, mcp_config_path)

        result.item("mcp-config.json", "success", f"{len(config_servers)} servers")
        if info.get("preserved"):
            names = ", ".join(sorted(info["preserved"]))
            result.item("User-added", "info", f"preserved: {names}")
        if info.get("overridden"):
            names = ", ".join(sorted(info["overridden"]))
            result.item("Overridden", "warn", f"managed replaced existing entry: {names}")
        if ctx.plugin_managed_names:
            managed = ", ".join(sorted(ctx.plugin_managed_names))
            result.item("Plugin-managed", "info", f"{managed} (via plugin .mcp.json)")
        return result
