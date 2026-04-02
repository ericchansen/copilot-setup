"""Step: Link repo skills into ~/.copilot/skills/."""

from __future__ import annotations

from copilotsetup.models import SetupContext, StepResult, UIShim
from copilotsetup.platform_ops import IS_WINDOWS, is_link, normalize_path, remove_link
from copilotsetup.skills import get_skill_folders, link_skills
from copilotsetup.sources import ConfigSource


def _under_prefix(path: str, prefix: str) -> bool:
    """Check if *path* is equal to or a child of *prefix* using a separator boundary."""
    prefix_sep = prefix if prefix.endswith("/") else prefix + "/"
    if IS_WINDOWS:
        return path.lower() == prefix.lower() or path.lower().startswith(prefix_sep.lower())
    return path == prefix or path.startswith(prefix_sep)


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

        # Clean up stale links for skills now handled by source-as-plugin
        # When a config source opts into asPlugin, its skills are discovered
        # through the plugin mechanism — remove old direct junctions/symlinks
        merged = getattr(ctx, "merged_config", None)
        if merged:
            plugin_paths = [normalize_path(sp["path"]) for sp in getattr(merged, "source_plugins", [])]
            if plugin_paths:
                skills_dir = ctx.copilot_skills
                if skills_dir.is_dir():
                    for entry in skills_dir.iterdir():
                        if is_link(entry):
                            target = normalize_path(str(entry.resolve()))
                            if any(_under_prefix(target, prefix) for prefix in plugin_paths):
                                remove_link(entry)
                                result.item(entry.name, "success", "removed — now handled by plugin")

        # Discover skills from ALL config sources with attribution
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
