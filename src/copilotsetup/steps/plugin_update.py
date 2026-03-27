"""Step: Update installed Copilot CLI plugins."""

from __future__ import annotations

from copilotsetup.models import SetupContext, StepResult, UIShim
from copilotsetup.skills import update_plugins


class PluginUpdateStep:
    """Run ``copilot plugin update`` on all installed plugins."""

    name = "Plugins · Update"

    def check(self, ctx: SetupContext) -> bool:
        return True

    def run(self, ctx: SetupContext) -> StepResult:
        result = StepResult()
        shim = UIShim()
        shim_summary: dict = {
            "plugins_updated": [],
            "plugins_update_skipped": [],
            "plugins_update_failed": [],
        }
        update_plugins(shim, shim_summary)

        for name, status, detail in shim.items:
            result.item(name, status, detail)
        return result
