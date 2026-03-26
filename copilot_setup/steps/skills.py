"""Step: Link repo skills into ~/.copilot/skills/."""

from __future__ import annotations

from copilot_setup.models import SetupContext, StepResult
from copilot_setup.ui_shim import UIShim
from lib.skills import get_skill_folders, link_skills


class SkillsStep:
    """Discover and symlink repo skills into ``~/.copilot/skills/``."""

    name = "Skills · Link"

    def check(self, ctx: SetupContext) -> bool:
        return True

    def run(self, ctx: SetupContext) -> StepResult:
        result = StepResult()
        shim = UIShim()
        shim_summary: dict = {
            "skills_created": [],
            "skills_existed": [],
            "skills_skipped": [],
            "skills_failed": [],
        }

        # Discover skills from ALL config sources, not just one repo
        all_skill_dirs = getattr(ctx, "all_skill_dirs", [ctx.repo_skills])
        all_skills: list[dict] = []
        for skill_dir in all_skill_dirs:
            all_skills.extend(get_skill_folders(skill_dir))

        ctx.local_skills = all_skills
        link_skills(shim, all_skills, ctx.copilot_skills, ctx.non_interactive, shim_summary)

        for name, status, detail in shim.items:
            result.item(name, status, detail)
        return result
