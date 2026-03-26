"""Step: Check/prompt MCP environment variables."""

from __future__ import annotations

from copilot_setup.models import SetupContext, StepResult


class McpEnvStep:
    """Verify required MCP server environment variables are set.

    Currently a no-op — env var requirements are not tracked in local.json.
    This step is retained as a hook for future use.
    """

    name = "MCP · Environment"

    def check(self, ctx: SetupContext) -> bool:
        return True

    def run(self, ctx: SetupContext) -> StepResult:
        return StepResult()
