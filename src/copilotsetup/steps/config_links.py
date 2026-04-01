"""Step: Symlink tracked config files into ~/.copilot/."""

from __future__ import annotations

from typing import ClassVar

from copilotsetup.models import SetupContext, StepResult
from copilotsetup.platform_ops import create_file_link


class ConfigLinksStep:
    """Create symlinks for tracked config files (e.g., copilot-instructions.md)."""

    name = "Setup · Config Symlinks"

    # Config files to link: name is the filename in ~/.copilot/,
    # target (optional) overrides the source filename in the repo.
    CONFIG_FILE_LINKS: ClassVar[list[dict[str, str]]] = [
        {"name": "copilot-instructions.md"},
    ]

    def check(self, ctx: SetupContext) -> bool:
        return True

    def run(self, ctx: SetupContext) -> StepResult:
        result = StepResult()

        # Use merged config for instructions path (first-wins from config sources)
        merged = getattr(ctx, "merged_config", None)

        for cfg in self.CONFIG_FILE_LINKS:
            source_name = cfg.get("target", cfg["name"])

            # Check merged instructions first, fall back to repo_copilot
            if source_name == "copilot-instructions.md" and merged and merged.instructions:
                target_path = merged.instructions
                # Find which source provided this
                src_label = _find_source_label(target_path, getattr(merged, "sources", [])) if merged else ""
            else:
                target_path = ctx.repo_copilot / source_name
                src_label = ""
            link_path = ctx.copilot_home / cfg["name"]

            if not target_path.exists():
                result.item(cfg["name"], "warn", "source not found in any config source")
                continue

            status = create_file_link(link_path, target_path, not ctx.non_interactive)
            provenance = f" (from {src_label})" if src_label else ""
            if status == "created":
                result.item(cfg["name"], "created", f"linked → {target_path}{provenance}")
            elif status == "copied":
                result.item(cfg["name"], "warn", f"copied (symlinks need Developer Mode){provenance}")
            elif status == "exists":
                result.item(cfg["name"], "exists", f"already linked{provenance}")
            elif status == "skipped":
                result.item(cfg["name"], "skipped", "user declined")
            else:
                result.item(cfg["name"], "failed", "could not create symlink")

        return result


def _find_source_label(path: str, sources: list) -> str:
    """Return 'source_name: source_path' for whichever source owns *path*."""
    from pathlib import Path as P

    resolved = P(path).resolve()
    for source in sources:
        if resolved.is_relative_to(source.path.resolve()):
            return f"{source.name}: {source.path}"
    return ""
