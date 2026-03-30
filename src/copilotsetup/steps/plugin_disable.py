"""Step: Register source-as-plugin entries and disable work plugins."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from copilotsetup.config import json_load_safe
from copilotsetup.models import SetupContext, StepResult
from copilotsetup.platform_ops import IS_WINDOWS


def _normalize(p: str) -> str:
    """Expand and normalize a path string for prefix matching."""
    return str(Path(p).expanduser().resolve()).replace("\\", "/").rstrip("/")


def _under_prefix(path: str, prefix: str) -> bool:
    """Check if *path* is equal to or a child of *prefix* using a separator boundary.

    Prevents ``/repos/agency`` matching ``/repos/agency2``.
    """
    prefix_sep = prefix if prefix.endswith("/") else prefix + "/"
    if IS_WINDOWS:
        return path.lower() == prefix.lower() or path.lower().startswith(prefix_sep.lower())
    return path == prefix or path.startswith(prefix_sep)


class PluginDisableStep:
    """Register config sources as plugins and disable work-only plugins.

    Two mechanisms:

    1. **Source-as-plugin** (``asPlugin`` in local.json): Registers the
       config source's ``.copilot/`` directory as a local plugin in
       ``config.json``.  Sources with an ``alias`` are disabled by default.

    2. **Disable by path** (``disablePluginsByPath``): Bulk-disables
       installed plugins whose ``cache_path`` falls under configured
       directory prefixes.
    """

    name = "Plugins · Disable by Path"

    def check(self, ctx: SetupContext) -> bool:
        merged = getattr(ctx, "merged_config", None)
        if not merged:
            return False
        return bool(merged.disable_plugin_paths) or bool(merged.source_plugins)

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

        # ── 1. Register source-as-plugin entries ─────────────────────
        for sp in merged.source_plugins:
            name = sp["name"]
            alias = sp.get("alias", "")
            plugin_path = sp["path"]
            enabled = not bool(alias)  # disabled if it has an alias

            if name not in registered_names:
                registered.append(
                    {
                        "name": name,
                        "marketplace": "local",
                        "version": "1.0.0",
                        "installed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "enabled": enabled,
                        "cache_path": plugin_path,
                    }
                )
                registered_names.add(name)
                config_dirty = True
                status = "disabled by default" if not enabled else "always enabled"
                result.item(name, "created", f"source plugin registered ({status})")
            else:
                # Update enabled state and path
                for entry in registered:
                    if entry.get("name") == name:
                        changed = False
                        if entry.get("cache_path") != plugin_path:
                            entry["cache_path"] = plugin_path
                            changed = True
                        if entry.get("enabled") != enabled:
                            entry["enabled"] = enabled
                            changed = True
                        if changed:
                            config_dirty = True
                            result.item(name, "success", "source plugin updated")
                        else:
                            result.item(name, "exists", "source plugin OK")
                        break

        # ── 2. Disable plugins by path prefix ────────────────────────
        prefixes = [_normalize(p) for p in merged.disable_plugin_paths]
        disabled_names: list[str] = []
        already_disabled: list[str] = []

        if prefixes:
            for entry in registered:
                if not isinstance(entry, dict):
                    continue
                cache_path = entry.get("cache_path", "")
                if not cache_path:
                    continue
                norm_cache = _normalize(cache_path)
                if any(_under_prefix(norm_cache, prefix) for prefix in prefixes):
                    name = entry.get("name", "unknown")
                    if entry.get("enabled", True):
                        entry["enabled"] = False
                        disabled_names.append(name)
                        config_dirty = True
                    else:
                        already_disabled.append(name)

        # Also disable aliased plugins from the plugins section
        # (install_plugins only disables on fresh install; this catches existing ones)
        for entry in registered:
            name = entry.get("name", "")
            plugin_info = merged.plugins.get(name)
            if plugin_info and plugin_info.get("alias") and entry.get("enabled", True):
                entry["enabled"] = False
                if name not in disabled_names:
                    disabled_names.append(name)
                config_dirty = True

        if disabled_names:
            for name in disabled_names:
                result.item(name, "success", "disabled by path rule")
        if already_disabled:
            for name in already_disabled:
                result.item(name, "exists", "already disabled")

        # ── 3. Remove work-only marketplaces from config.json ──────
        work_marketplaces = getattr(merged, "marketplaces", {})
        if work_marketplaces:
            existing_marketplaces = config_obj.get("marketplaces", {})
            removed_mkt: list[str] = []
            for mkt_name in work_marketplaces:
                if mkt_name in existing_marketplaces:
                    del existing_marketplaces[mkt_name]
                    removed_mkt.append(mkt_name)
                    config_dirty = True
            if removed_mkt:
                config_obj["marketplaces"] = existing_marketplaces
                for name in removed_mkt:
                    result.item(f"marketplace:{name}", "success", "removed — work-only")

        # Write config.json if anything changed
        if config_dirty:
            config_obj["installed_plugins"] = registered
            ctx.config_json.write_text(json.dumps(config_obj, indent=2) + "\n", "utf-8")

        # Store disabled plugin names on context for alias step
        # Include source-plugins with aliases + path-disabled + alias-disabled
        all_disabled = set(disabled_names) | set(already_disabled)
        for sp in merged.source_plugins:
            if sp.get("alias"):
                all_disabled.add(sp["name"])
        ctx.disabled_plugin_names = all_disabled  # type: ignore[attr-defined]

        # Store work marketplaces on context for alias step
        ctx.work_marketplaces = work_marketplaces  # type: ignore[attr-defined]

        return result
