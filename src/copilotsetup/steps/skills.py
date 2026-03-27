"""Step: Link repo skills into ~/.copilot/skills/."""

from __future__ import annotations

from copilotsetup.models import SetupContext, StepResult, UIShim
from copilotsetup.skills import get_skill_folders, link_skills
from copilotsetup.sources import ConfigSource


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

        # Discover skills from ALL config sources with attribution
        merged = getattr(ctx, "merged_config", None)
        sources: list[ConfigSource] = merged.sources if merged else []
        all_skill_dirs = getattr(ctx, "all_skill_dirs", [ctx.repo_skills])
        all_skills: list[dict] = []

        for skill_dir in all_skill_dirs:
            # Find which source owns this skill_dir
            source_name = _source_name_for_dir(skill_dir, sources)
            skills = get_skill_folders(skill_dir)
            if skills:
                result.item(f"[{source_name}]", "info", f"{len(skills)} skill(s) from {skill_dir}")
            all_skills.extend(skills)

        ctx.local_skills = all_skills
        link_skills(shim, all_skills, ctx.copilot_skills, ctx.non_interactive, shim_summary)

        for name, status, detail in shim.items:
            result.item(name, status, detail)
        return result


def _source_name_for_dir(skill_dir, sources: list[ConfigSource]) -> str:
    """Find the config source name that owns a given skill directory."""
    from pathlib import Path

    resolved = Path(skill_dir).resolve()
    for source in sources:
        if resolved.is_relative_to(source.path.resolve()):
            return source.name
    return "unknown"
