"""Step: Backup ~/.copilot/ before making changes."""

from __future__ import annotations

from copilotsetup.backup import backup_copilot_home
from copilotsetup.models import SetupContext, StepResult, UIShim


class BackupStep:
    """Back up ``~/.copilot/`` config files and skills."""

    name = "Backup"

    def check(self, ctx: SetupContext) -> bool:
        return True

    def run(self, ctx: SetupContext) -> StepResult:
        result = StepResult()
        shim = UIShim()
        shim_summary: dict = {"backed_up": False, "backup_dir": ""}
        backup_copilot_home(shim, ctx.copilot_home, shim_summary)

        for name, status, detail in shim.items:
            result.item(name, status, detail)
        return result
