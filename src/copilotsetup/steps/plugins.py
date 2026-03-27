"""Step: Install and register Copilot CLI plugins."""

from __future__ import annotations

from pathlib import Path

from copilotsetup.models import SetupContext, StepResult, UIShim
from copilotsetup.skills import install_plugins, link_local_plugins


class PluginsStep:
    """Install Copilot CLI plugins and register local clones."""

    name = "Skills · Plugins"

    def check(self, ctx: SetupContext) -> bool:
        return True

    def run(self, ctx: SetupContext) -> StepResult:
        result = StepResult()
        shim = UIShim()
        shim_summary: dict = {"plugins_installed": [], "plugins_skipped": [], "plugins_failed": []}

        # Plugins come from local.json in config sources
        merged = getattr(ctx, "merged_config", None)
        all_plugins = merged.plugins if merged else {}
        local_paths = merged.local_paths if merged else {}

        # Show where plugins are defined (respecting first-wins merge semantics)
        if all_plugins and merged:
            seen_plugins: set[str] = set()
            for source in getattr(merged, "sources", []):
                if not getattr(source, "plugins", None):
                    continue
                effective = sorted(name for name in source.plugins if name in all_plugins and name not in seen_plugins)
                if not effective:
                    continue
                seen_plugins.update(effective)
                names = ", ".join(effective)
                result.item(f"[{source.name}]", "info", f"plugins: {names} (from {source.path})")

        if not all_plugins:
            result.item("Plugins", "info", "no plugins defined")
            return result

        # Install all declared plugins. Previously this was gated on enabled_servers,
        # but plugins.json is an explicit declaration — install them all.
        plugins_to_install = [
            {"name": name, "source": info.get("source", ""), "localServerName": name, "alias": info.get("alias", "")}
            for name, info in all_plugins.items()
            if info.get("source")
        ]

        if not plugins_to_install:
            result.item("Plugins", "info", "no plugin sources defined")
            return result

        # Resolve local clones using local_paths from local.json
        local_clone_map: dict[str, Path] = {}
        for plugin in plugins_to_install:
            server_name = plugin["localServerName"]
            local_path = local_paths.get(server_name)
            if not local_path:
                continue
            candidate = Path(local_path).expanduser()
            if candidate.is_dir() and (candidate / ".git").is_dir():
                local_clone_map[plugin["name"]] = candidate

        install_plugins(shim, plugins_to_install, local_clone_map, shim_summary)

        if local_clone_map:
            link_local_plugins(shim, plugins_to_install, local_clone_map, ctx.config_json, shim_summary)

        ctx.local_clone_map = local_clone_map
        ctx.plugins_to_install = plugins_to_install

        # Only mark servers as plugin-managed when the plugin is confirmed
        confirmed_plugin_names = set(shim_summary["plugins_installed"]) | set(shim_summary["plugins_skipped"])
        ctx.plugin_server_names = {
            p["localServerName"]
            for p in plugins_to_install
            if p.get("localServerName") and (p["name"] in confirmed_plugin_names or p["name"] in local_clone_map)
        }

        for name, status, detail in shim.items:
            result.item(name, status, detail)
        return result
