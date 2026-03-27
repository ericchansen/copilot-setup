"""Step implementations for the setup pipeline.

Import all steps here for convenient access from the runner.
"""

from copilotsetup.steps.backup import BackupStep
from copilotsetup.steps.config_links import ConfigLinksStep
from copilotsetup.steps.config_patch import ConfigPatchStep
from copilotsetup.steps.directories import DirectoriesStep
from copilotsetup.steps.git_auth import GitAuthStep
from copilotsetup.steps.lsp_config import LspConfigStep
from copilotsetup.steps.mcp_build import McpBuildStep
from copilotsetup.steps.mcp_config import McpConfigStep
from copilotsetup.steps.plugin_update import PluginUpdateStep
from copilotsetup.steps.plugins import PluginsStep
from copilotsetup.steps.shell_alias import ShellAliasStep
from copilotsetup.steps.skills import SkillsStep
from copilotsetup.steps.stale_cleanup import CleanupStep
from copilotsetup.steps.trusted_folders import TrustedFoldersStep

# Ordered list of all setup steps — matches the original _run_setup() flow.
ALL_STEPS = [
    GitAuthStep(),
    BackupStep(),
    DirectoriesStep(),
    ConfigLinksStep(),
    ConfigPatchStep(),
    TrustedFoldersStep(),
    SkillsStep(),
    PluginsStep(),
    PluginUpdateStep(),
    ShellAliasStep(),
    McpBuildStep(),
    McpConfigStep(),
    LspConfigStep(),
    CleanupStep(),
]

__all__ = [
    "ALL_STEPS",
    "BackupStep",
    "CleanupStep",
    "ConfigLinksStep",
    "ConfigPatchStep",
    "DirectoriesStep",
    "GitAuthStep",
    "LspConfigStep",
    "McpBuildStep",
    "McpConfigStep",
    "PluginUpdateStep",
    "PluginsStep",
    "ShellAliasStep",
    "SkillsStep",
    "TrustedFoldersStep",
]
