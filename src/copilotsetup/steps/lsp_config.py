"""Step: Generate lsp-config.json."""

from __future__ import annotations

from copilotsetup.config import generate_lsp_config
from copilotsetup.models import SetupContext, StepResult, UIShim


class LspConfigStep:
    """Validate LSP server binaries and generate ``~/.copilot/lsp-config.json``."""

    name = "LSP · Config"

    def check(self, ctx: SetupContext) -> bool:
        return True

    def run(self, ctx: SetupContext) -> StepResult:
        result = StepResult()
        shim = UIShim()
        lsp_config_path = ctx.copilot_home / "lsp-config.json"

        # LSP servers come from merged sources (first-wins)
        merged = getattr(ctx, "merged_config", None)
        if merged and merged.lsp_servers and merged.lsp_servers_path:
            lsp_json_path = merged.lsp_servers_path
        else:
            lsp_json_path = ctx.lsp_servers_json

        lsp_count, lsp_skipped = generate_lsp_config(lsp_json_path, lsp_config_path, shim)
        ctx.lsp_count = lsp_count
        ctx.lsp_skipped = lsp_skipped

        for name, status, detail in shim.items:
            result.item(name, status, detail)
        return result
