"""Step: Install and register Copilot CLI plugins."""

from __future__ import annotations

from pathlib import Path

from copilot_setup.models import SetupContext, StepResult
from copilot_setup.ui_shim import UIShim
from lib.skills import install_plugins, link_local_plugins


class PluginsStep:
    """Install Copilot CLI plugins and register local clones."""

    name = "Skills · Plugins"

    def check(self, ctx: SetupContext) -> bool:
        return True

    def run(self, ctx: SetupContext) -> StepResult:
        result = StepResult()
        shim = UIShim()
        shim_summary: dict = {"plugins_installed": [], "plugins_skipped": [], "plugins_failed": []}

        # Plugins come pre-merged from config sources
        plugins_to_install = getattr(ctx, "merged_plugins", [])
        if not plugins_to_install:
            result.item("Plugins", "info", "no plugins in config sources")
            return result

        # Resolve local clones from merged server list
        enabled_servers = getattr(ctx, "enabled_servers", [])
        local_clone_map: dict[str, Path] = {}
        for plugin in plugins_to_install:
            local_name = plugin.get("localServerName")
            if not local_name:
                continue
            server_def = next((s for s in enabled_servers if s["name"] == local_name), None)
            if not server_def:
                continue
            entry_point = server_def.get("entryPoint", "")
            for dp in server_def.get("defaultPaths", []):
                candidate = Path(dp).expanduser()
                if (
                    candidate.is_dir()
                    and (candidate / ".git").is_dir()
                    and (not entry_point or (candidate / entry_point).exists())
                ):
                    local_clone_map[plugin["name"]] = candidate
                    break

        install_plugins(shim, plugins_to_install, local_clone_map, shim_summary)

        if local_clone_map:
            link_local_plugins(shim, plugins_to_install, local_clone_map, ctx.config_json, shim_summary)

        ctx.local_clone_map = local_clone_map
        ctx.plugins_to_install = plugins_to_install

        # Only mark servers as plugin-managed when the plugin is confirmed
        # available — installed, already present, or backed by a local clone.
        confirmed_plugin_names = set(shim_summary["plugins_installed"]) | set(shim_summary["plugins_skipped"])
        ctx.plugin_server_names = {
            p["localServerName"]
            for p in plugins_to_install
            if p.get("localServerName") and (p["name"] in confirmed_plugin_names or p["name"] in local_clone_map)
        }

        for name, status, detail in shim.items:
            result.item(name, status, detail)
        return result
