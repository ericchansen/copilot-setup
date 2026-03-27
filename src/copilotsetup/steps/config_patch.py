"""Step: Merge portable settings into config.json."""

from __future__ import annotations

from copilotsetup.config import patch_config_json
from copilotsetup.models import SetupContext, StepResult

# Keys allowed to be copied from config.portable.json → config.json
PORTABLE_ALLOWED_KEYS = [
    "banner",
    "model",
    "render_markdown",
    "theme",
    "experimental",
    "reasoning_effort",
]


class ConfigPatchStep:
    """Patch ``~/.copilot/config.json`` with portable settings."""

    name = "Setup · Patch config.json"

    def check(self, ctx: SetupContext) -> bool:
        return True

    def run(self, ctx: SetupContext) -> StepResult:
        result = StepResult()

        # Portable config comes from merged sources (first-wins)
        merged = getattr(ctx, "merged_config", None)
        portable = merged.portable_config if merged else ctx.portable_json

        # Show which source provided portable config
        if merged and merged.portable_config:
            for source in getattr(merged, "sources", []):
                if source.portable_config and source.portable_config == merged.portable_config:
                    result.item(f"[{source.name}]", "info", f"portable config from {source.path}")
                    break

        patched = patch_config_json(ctx.config_json, portable, PORTABLE_ALLOWED_KEYS)
        if patched:
            result.item("config.json", "success", "patched with portable settings")
        else:
            result.item("config.portable.json", "warn", "not found — skipping patch")
        return result
