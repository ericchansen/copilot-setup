"""Step: Clone/build local MCP servers."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from copilot_setup.models import SetupContext, StepResult
from lib.build_detect import detect_build_commands


class McpBuildStep:
    """Build local MCP servers that have paths in local.json."""

    name = "MCP · Build Servers"

    def check(self, ctx: SetupContext) -> bool:
        return True

    def run(self, ctx: SetupContext) -> StepResult:
        result = StepResult()

        enabled = getattr(ctx, "enabled_servers", {})
        merged = getattr(ctx, "merged_config", None)
        local_paths = merged.local_paths if merged else {}

        # Compute plugin-managed names (servers with plugins confirmed in plugin step)
        plugin_server_names = getattr(ctx, "plugin_server_names", set())
        local_clone_map: dict[str, Path] = getattr(ctx, "local_clone_map", {})
        ctx.plugin_managed_names = {
            name for name in enabled
            if name in plugin_server_names and name not in local_clone_map
        }

        # Load stored paths from previous runs
        mcp_paths_file = ctx.copilot_home / ".mcp-paths.json"
        try:
            mcp_paths: dict = json.loads(mcp_paths_file.read_text("utf-8")) if mcp_paths_file.exists() else {}
        except json.JSONDecodeError:
            mcp_paths = {}

        failed_names: list[str] = []
        any_buildable = False

        for name in enabled:
            local_path_str = local_paths.get(name)
            if not local_path_str:
                continue  # No local path → server is ready-to-use (npx, HTTP, or plugin)

            any_buildable = True

            # Plugin-managed server without local clone → plugin handles everything
            if name in ctx.plugin_managed_names:
                result.item(name, "info", "handled by plugin — skipping build")
                continue

            expanded = Path(local_path_str).expanduser().resolve()

            # Check stored path first, then local.json path
            stored = mcp_paths.get(name)
            if stored and Path(stored).exists():
                resolved_path = stored
                result.item(name, "info", f"using stored path: {resolved_path}")
            elif expanded.exists():
                resolved_path = str(expanded)
            else:
                result.item(name, "warning", f"local path not found: {expanded}")
                continue

            mcp_paths[name] = resolved_path

            # Auto-detect and run build
            build_cmds = detect_build_commands(Path(resolved_path))
            if build_cmds:
                build_ok = True
                for cmd in build_cmds:
                    r = subprocess.run(
                        cmd,
                        shell=True,
                        cwd=resolved_path,
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                    )
                    if r.returncode != 0:
                        result.item(name, "failed", f"'{cmd}' failed (exit {r.returncode})")
                        build_ok = False
                        break
                if build_ok:
                    result.item(name, "success", "built")
                else:
                    failed_names.append(name)
            else:
                result.item(name, "info", f"no build needed — {resolved_path}")

        # Remove failed builds from enabled servers
        for n in failed_names:
            enabled.pop(n, None)

        mcp_paths_file.write_text(json.dumps(mcp_paths, indent=2) + "\n", "utf-8")
        ctx.mcp_paths = mcp_paths

        if not any_buildable:
            result.item("Local MCP servers", "info", "none to build")

        return result
