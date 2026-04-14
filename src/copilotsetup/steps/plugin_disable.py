"""Step: Register config sources as local plugins in config.json."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from copilotsetup.config import json_load_safe
from copilotsetup.models import SetupContext, StepResult


class PluginRegisterStep:
    """Register config sources as local plugins in config.json.

    For each source with ``asPlugin`` or ``plugin.json``, ensures an entry
    exists in ``config.json``'s ``installed_plugins`` list with the correct
    path and ``enabled: True``.
    """

    name = "Plugins · Register Sources"

    def check(self, ctx: SetupContext) -> bool:
        merged = getattr(ctx, "merged_config", None)
        if not merged:
            return False
        return bool(merged.source_plugins)

    def run(self, ctx: SetupContext) -> StepResult:
        result = StepResult()
        merged = getattr(ctx, "merged_config", None)
        if not merged:
            return result

        config_obj = json_load_safe(ctx.config_json)
        registered: list[dict] = config_obj.get("installed_plugins", [])
        if not isinstance(registered, list):
            registered = []
        registered_names = {p.get("name") for p in registered if isinstance(p, dict)}
        config_dirty = False

        for sp in merged.source_plugins:
            name = sp["name"]
            plugin_path = sp["path"]

            if name not in registered_names:
                registered.append(
                    {
                        "name": name,
                        "marketplace": "local",
                        "version": "1.0.0",
                        "installed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "enabled": True,
                        "cache_path": plugin_path,
                    }
                )
                registered_names.add(name)
                config_dirty = True
                result.item(name, "created", "source plugin registered")
            else:
                for entry in registered:
                    if not isinstance(entry, dict):
                        continue
                    if entry.get("name") == name:
                        changed = False
                        if entry.get("cache_path") != plugin_path:
                            entry["cache_path"] = plugin_path
                            changed = True
                        if not entry.get("enabled", True):
                            entry["enabled"] = True
                            changed = True
                        if changed:
                            config_dirty = True
                            result.item(name, "success", "source plugin updated")
                        else:
                            result.item(name, "exists", "source plugin OK")
                        break

        if config_dirty:
            config_obj["installed_plugins"] = registered
            ctx.config_json.write_text(json.dumps(config_obj, indent=2) + "\n", "utf-8")

        return result
