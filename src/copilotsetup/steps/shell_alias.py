"""Step: Create shell aliases for disabled-by-default plugins."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from copilotsetup.models import SetupContext, StepResult
from copilotsetup.platform_ops import IS_WINDOWS

# Marker comments so we can detect and update our managed blocks
_BLOCK_START = "# >>> copilot-config managed: {alias} >>>"
_BLOCK_END = "# <<< copilot-config managed: {alias} <<<"

_PS_TEMPLATE = """\
{block_start}
function {alias} {{
    $configPath = Join-Path $env:USERPROFILE ".copilot" "config.json"
    if (-not (Test-Path -Path $configPath -PathType Leaf)) {{
        Write-Error "Copilot config not found at $configPath."
        return
    }}
    try {{
        $config = Get-Content $configPath -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
    }} catch {{
        Write-Error "Failed to parse Copilot config at $configPath."
        return
    }}
    $pluginNames = @({plugin_names_ps})
    $toggled = @()
    foreach ($p in $config.installed_plugins) {{
        if ($pluginNames -contains $p.name -and -not $p.enabled) {{
            $p.enabled = $true
            $toggled += $p.name
        }}
    }}{marketplace_ps_enable}
    if ($toggled.Count -gt 0{marketplace_ps_changed}) {{
        $config | ConvertTo-Json -Depth 10 | Set-Content $configPath -Encoding UTF8
    }}
    try {{
        copilot @args
    }} finally {{
        if ($toggled.Count -gt 0{marketplace_ps_changed}) {{
            $config = Get-Content $configPath -Raw | ConvertFrom-Json
            foreach ($p in $config.installed_plugins) {{
                if ($toggled -contains $p.name) {{
                    $p.enabled = $false
                }}
            }}{marketplace_ps_disable}
            $config | ConvertTo-Json -Depth 10 | Set-Content $configPath -Encoding UTF8
        }}
    }}
}}
{block_end}
"""

_BASH_TEMPLATE = """\
{block_start}
{alias}() {{
    local config_path="$HOME/.copilot/config.json"
    if [ ! -f "$config_path" ]; then
        echo "Error: Copilot config not found at $config_path." >&2
        return 1
    fi
    local _py
    for _py in python3 python py; do
        if command -v "$_py" >/dev/null 2>&1; then break; fi
        _py=""
    done
    if [ -z "$_py" ]; then
        echo "Error: Python not found. Install Python 3.10+ to use {alias}." >&2
        return 1
    fi
    local _toggled
    _toggled=$("$_py" -c "
import json
config = json.load(open('$config_path'))
names = {plugin_names_py}
toggled = []
for p in config.get('installed_plugins', []):
    if p['name'] in names and not p.get('enabled', True):
        p['enabled'] = True
        toggled.append(p['name'])
{marketplace_py_enable}json.dump(config, open('$config_path', 'w'), indent=2)
print(','.join(toggled))
" 2>/dev/null)
    _copilot_exit=0
    copilot "$@" || _copilot_exit=$?
    "$_py" -c "
import json
config = json.load(open('$config_path'))
toggled = set('$_toggled'.split(',')) if '$_toggled' else set()
for p in config.get('installed_plugins', []):
    if p['name'] in toggled:
        p['enabled'] = False
{marketplace_py_disable}json.dump(config, open('$config_path', 'w'), indent=2)
" 2>/dev/null
    return $_copilot_exit
}}
{block_end}
"""

# Developer variant: point directly at the local clone (single plugin)
_PS_DEV_TEMPLATE = """\
{block_start}
function {alias} {{
    copilot --plugin-dir "{clone_path}" @args
}}
{block_end}
"""

_BASH_DEV_TEMPLATE = """\
{block_start}
{alias}() {{
    copilot --plugin-dir "{clone_path}" "$@"
}}
{block_end}
"""


def _profile_path_ps() -> Path | None:
    """Return the PowerShell profile path (CurrentUserCurrentHost).

    Handles OneDrive Known Folder Move by checking the shell folder registry
    key for the real Documents path, then falling back to ``USERPROFILE/Documents``.
    """
    import winreg

    raw = os.environ.get("USERPROFILE")
    if not raw:
        return None

    # Try registry for the real Documents path (handles OneDrive redirection)
    docs = None
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
        ) as key:
            val, _ = winreg.QueryValueEx(key, "Personal")
            docs = Path(os.path.expandvars(val))
    except OSError:
        pass

    if not docs or not docs.is_dir():
        docs = Path(raw) / "Documents"

    ps7 = docs / "PowerShell" / "Microsoft.PowerShell_profile.ps1"
    ps5 = docs / "WindowsPowerShell" / "Microsoft.PowerShell_profile.ps1"
    # Prefer whichever already exists; default to PS7
    if ps5.exists() and not ps7.exists():
        return ps5
    return ps7


def _profile_paths_unix() -> list[Path]:
    """Return candidate shell profile paths on Unix."""
    home = Path.home()
    candidates = []
    # Prefer zsh on macOS, bash elsewhere
    zshrc = home / ".zshrc"
    bashrc = home / ".bashrc"
    if zshrc.exists():
        candidates.append(zshrc)
    if bashrc.exists():
        candidates.append(bashrc)
    if not candidates:
        candidates.append(bashrc)  # Default to .bashrc
    return candidates


def _has_alias_block(content: str, alias: str) -> bool:
    """Check if the managed alias block already exists in the profile content."""
    start = _BLOCK_START.format(alias=alias)
    return start in content


def _remove_alias_block(content: str, alias: str) -> str:
    """Remove an existing managed alias block from profile content."""
    start = re.escape(_BLOCK_START.format(alias=alias))
    end = re.escape(_BLOCK_END.format(alias=alias))
    pattern = rf"\n?{start}.*?{end}\n?"
    return re.sub(pattern, "\n", content, flags=re.DOTALL)


def _append_alias(profile_path: Path, block: str) -> bool:
    """Append an alias block to a shell profile, creating it if needed."""
    try:
        profile_path.parent.mkdir(parents=True, exist_ok=True)

        content = profile_path.read_text("utf-8") if profile_path.exists() else ""
        # Remove old block if present (allows updates)
        alias_match = re.search(r"function (\S+)", block) or re.search(r"^(\S+)\(\)", block, re.MULTILINE)
        if alias_match:
            alias_name = alias_match.group(1)
            if _has_alias_block(content, alias_name):
                content = _remove_alias_block(content, alias_name)

        # Append new block
        if not content.endswith("\n"):
            content += "\n"
        content += block
        profile_path.write_text(content, "utf-8")
    except OSError:
        return False
    return True


class ShellAliasStep:
    """Create shell aliases for disabled-by-default plugins (e.g., copilot-work)."""

    name = "Setup · Shell Aliases"

    def check(self, ctx: SetupContext) -> bool:
        merged = getattr(ctx, "merged_config", None)
        if not merged:
            return False
        has_alias_plugins = any(info.get("alias") for info in merged.plugins.values())
        has_source_plugins = any(sp.get("alias") for sp in getattr(merged, "source_plugins", []))
        return has_alias_plugins or has_source_plugins

    def run(self, ctx: SetupContext) -> StepResult:
        result = StepResult()

        merged = getattr(ctx, "merged_config", None)
        if not merged:
            return result

        # Group all disabled plugin names by alias
        # 1. Plugins with explicit alias in local.json
        alias_groups: dict[str, set[str]] = {}
        alias_clone_paths: dict[str, Path] = {}  # alias → clone path (dev mode)

        for name, info in merged.plugins.items():
            alias = info.get("alias")
            if not alias:
                continue
            alias_groups.setdefault(alias, set()).add(name)
            clone = ctx.local_clone_map.get(name)
            if clone:
                alias_clone_paths[alias] = clone

        # 2. Plugins disabled by path (from PluginDisableStep)
        disabled_names: set[str] = getattr(ctx, "disabled_plugin_names", set())
        # Find which alias to associate path-disabled plugins with
        # Check explicit plugins first, then source-as-plugins
        primary_alias = None
        for info in merged.plugins.values():
            if info.get("alias"):
                primary_alias = info["alias"]
                break
        if not primary_alias:
            for sp in getattr(merged, "source_plugins", []):
                if sp.get("alias"):
                    primary_alias = sp["alias"]
                    break

        if primary_alias and disabled_names:
            alias_groups.setdefault(primary_alias, set()).update(disabled_names)

        if not alias_groups:
            return result

        for alias, plugin_names in alias_groups.items():
            clone_path = alias_clone_paths.get(alias)

            # Dev mode: single plugin with local clone → simple --plugin-dir alias
            if clone_path and len(plugin_names) == 1:
                fmt = {
                    "alias": alias,
                    "clone_path": str(clone_path),
                    "block_start": _BLOCK_START.format(alias=alias),
                    "block_end": _BLOCK_END.format(alias=alias),
                }
                if IS_WINDOWS:
                    block = _PS_DEV_TEMPLATE.format(**fmt)
                    profile = _profile_path_ps()
                    if not profile:
                        result.item(alias, "failed", "could not determine PowerShell profile path")
                        continue
                    if _append_alias(profile, block):
                        result.item(alias, "created", f"dev alias → {clone_path}")
                    else:
                        result.item(alias, "failed", f"could not write to {profile}")
                else:
                    block = _BASH_DEV_TEMPLATE.format(**fmt)
                    profiles = _profile_paths_unix()
                    wrote = [p for p in profiles if _append_alias(p, block)]
                    if wrote:
                        result.item(alias, "created", f"dev alias → {clone_path}")
                continue

            # Standard mode: enable/disable multiple plugins via config.json
            sorted_names = sorted(plugin_names)
            plugin_names_ps = ", ".join(f'"{n}"' for n in sorted_names)
            plugin_names_py = repr(set(sorted_names))

            # Marketplace snippets (add on enable, remove on disable)
            work_marketplaces: dict = getattr(ctx, "work_marketplaces", {})
            if work_marketplaces:
                mkt_json = json.dumps(work_marketplaces)
                mkt_names_ps = ", ".join(f'"{n}"' for n in work_marketplaces)
                mkt_keys_py = repr(list(work_marketplaces.keys()))
                marketplace_ps_enable = (
                    "\n    if (-not $config.marketplaces) {{ "
                    "$config | Add-Member -NotePropertyName 'marketplaces' -NotePropertyValue ([PSCustomObject]@{{}}) }}"
                    f"\n    $mkt = '{mkt_json}' | ConvertFrom-Json"
                    "\n    foreach ($prop in $mkt.PSObject.Properties) {{ "
                    "$config.marketplaces | Add-Member -NotePropertyName $prop.Name -NotePropertyValue $prop.Value -Force }}"
                )
                marketplace_ps_changed = " -or $true"  # marketplace always needs cleanup
                marketplace_ps_disable = (
                    f"\n            $mktNames = @({mkt_names_ps})"
                    "\n            foreach ($mn in $mktNames) {{ $config.marketplaces.PSObject.Properties.Remove($mn) }}"
                )
                marketplace_py_enable = f"mkt = {mkt_json}\nconfig.setdefault('marketplaces', {{{{}}}}).update(mkt)\n"
                marketplace_py_disable = (
                    f"for mn in {mkt_keys_py}:\n    config.get('marketplaces', {{{{}}}}).pop(mn, None)\n"
                )
            else:
                marketplace_ps_enable = ""
                marketplace_ps_changed = ""
                marketplace_ps_disable = ""
                marketplace_py_enable = ""
                marketplace_py_disable = ""

            fmt = {
                "alias": alias,
                "plugin_names_ps": plugin_names_ps,
                "plugin_names_py": plugin_names_py,
                "marketplace_ps_enable": marketplace_ps_enable,
                "marketplace_ps_changed": marketplace_ps_changed,
                "marketplace_ps_disable": marketplace_ps_disable,
                "marketplace_py_enable": marketplace_py_enable,
                "marketplace_py_disable": marketplace_py_disable,
                "block_start": _BLOCK_START.format(alias=alias),
                "block_end": _BLOCK_END.format(alias=alias),
            }

            if IS_WINDOWS:
                profile = _profile_path_ps()
                if not profile:
                    result.item(alias, "failed", "could not determine PowerShell profile path")
                    continue
                block = _PS_TEMPLATE.format(**fmt)
                if _append_alias(profile, block):
                    result.item(alias, "created", f"alias ({len(sorted_names)} plugins) → {profile.name}")
                else:
                    result.item(alias, "failed", f"could not write to {profile}")
            else:
                block = _BASH_TEMPLATE.format(**fmt)
                profiles = _profile_paths_unix()
                wrote = [p for p in profiles if _append_alias(p, block)]
                failed = [p for p in profiles if p not in wrote]
                if wrote:
                    result.item(
                        alias, "created", f"alias ({len(sorted_names)} plugins) → {', '.join(p.name for p in wrote)}"
                    )
                if failed:
                    result.item(alias, "failed", f"could not write to {', '.join(str(p) for p in failed)}")

        return result
