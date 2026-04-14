"""Step: Legacy + stale/orphaned skill cleanup from ~/.copilot/skills/."""

from __future__ import annotations

from copilotsetup.models import SetupContext, StepResult, UIShim
from copilotsetup.skills import cleanup_stale, legacy_cleanup

LEGACY_PATTERNS = ["anthropic-skills", "awesome-copilot", "SPT-IQ"]


class CleanupStep:
    """Remove legacy junctions and broken/unmanaged skill symlinks."""

    name = "Cleanup · Skills"

    def check(self, ctx: SetupContext) -> bool:
        return True

    def run(self, ctx: SetupContext) -> StepResult:
        result = StepResult()
        shim = UIShim()

        # Legacy junction cleanup
        legacy_summary: dict = {"plugin_junctions_cleaned": 0}
        legacy_cleanup(shim, ctx.copilot_skills, ctx.repo_root, LEGACY_PATTERNS, legacy_summary)

        # Stale/orphan cleanup
        stale_summary: dict = {}
        linked_names = {s["name"] for s in getattr(ctx, "local_skills", [])}
        auto_remove = ctx.include_clean_orphans or ctx.non_interactive

        cleanup_stale(
            shim,
            ctx.copilot_skills,
            linked_names,
            ctx.repo_root,
            ctx.external_dir,
            ctx.include_clean_orphans,
            auto_remove,
            stale_summary,
        )

        for name, status, detail in shim.items:
            result.item(name, status, detail)

        return result
