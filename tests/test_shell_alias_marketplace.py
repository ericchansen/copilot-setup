"""Tests for marketplace snippet generation in ShellAliasStep."""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import patch

from copilotsetup.steps.shell_alias import ShellAliasStep


class _FakeMerged:
    """Minimal merged config with one aliased plugin."""

    def __init__(self) -> None:
        self.plugins: dict[str, dict] = {"work-plugin": {"alias": "copilot-work"}}
        self.source_plugins: list[dict] = []


class _FakeCtx:
    """Minimal context wired for the marketplace code path."""

    def __init__(self, marketplaces: dict) -> None:
        merged = _FakeMerged()
        self.merged_config = merged
        self.local_clone_map: dict[str, Path] = {}
        self.disabled_plugin_names: set[str] = set()
        self.work_marketplaces = marketplaces


SAMPLE_MARKETPLACES = {
    "contoso": {"url": "https://contoso.example.com/marketplace"},
}


def _strip_json_strings(text: str) -> str:
    """Remove single-quoted JSON blobs so we only inspect PS code braces."""
    return re.sub(r"'[^']*'", "''", text)


class TestMarketplaceSnippetPS:
    """Verify generated PowerShell profile has correct brace syntax."""

    def test_no_double_braces_in_ps_code(self, tmp_path: Path) -> None:
        """Marketplace snippets must produce single { } in PS code.

        The bug was {{ }} appearing in script-block / hashtable positions
        because the snippet strings were accidentally treated as .format()
        templates.  We strip embedded JSON strings (which may legitimately
        contain }}) before asserting.
        """
        ps_profile = tmp_path / "Microsoft.PowerShell_profile.ps1"
        ctx = _FakeCtx(SAMPLE_MARKETPLACES)

        with (
            patch("copilotsetup.steps.shell_alias.IS_WINDOWS", True),
            patch("copilotsetup.steps.shell_alias._profile_path_ps", return_value=ps_profile),
        ):
            result = ShellAliasStep().run(ctx)

        assert any(i.status == "created" for i in result.items), f"step failed: {result.items}"

        content = ps_profile.read_text("utf-8")
        code_only = _strip_json_strings(content)

        assert "{{" not in code_only, f"double open-brace in PS code:\n{content}"
        assert "}}" not in code_only, f"double close-brace in PS code:\n{content}"

    def test_ps_has_proper_hashtable_and_scriptblocks(self, tmp_path: Path) -> None:
        ps_profile = tmp_path / "Microsoft.PowerShell_profile.ps1"
        ctx = _FakeCtx(SAMPLE_MARKETPLACES)

        with (
            patch("copilotsetup.steps.shell_alias.IS_WINDOWS", True),
            patch("copilotsetup.steps.shell_alias._profile_path_ps", return_value=ps_profile),
        ):
            ShellAliasStep().run(ctx)

        content = ps_profile.read_text("utf-8")

        # PowerShell empty hashtable — marketplace enable snippet
        assert "@{}" in content, "missing @{} (empty hashtable)"
        # Script-block style braces from marketplace snippets
        assert "{ $config" in content, "missing '{ $config' script block"
        assert "{ $config.marketplaces" in content, "missing marketplace Add-Member block"


class TestMarketplaceSnippetBash:
    """Verify generated bash/Python profile has correct brace syntax."""

    def test_no_double_braces_in_bash_output(self, tmp_path: Path) -> None:
        bashrc = tmp_path / ".bashrc"
        bashrc.write_text("", "utf-8")
        ctx = _FakeCtx(SAMPLE_MARKETPLACES)

        with (
            patch("copilotsetup.steps.shell_alias.IS_WINDOWS", False),
            patch("copilotsetup.steps.shell_alias._profile_paths_unix", return_value=[bashrc]),
        ):
            result = ShellAliasStep().run(ctx)

        assert any(i.status == "created" for i in result.items), f"step failed: {result.items}"

        content = bashrc.read_text("utf-8")

        # Python dict literals must be {} not {{}}
        assert "{{}}" not in content, f"found '{{{{}}}}' in bash profile:\n{content}"

    def test_bash_has_proper_empty_dicts(self, tmp_path: Path) -> None:
        bashrc = tmp_path / ".bashrc"
        bashrc.write_text("", "utf-8")
        ctx = _FakeCtx(SAMPLE_MARKETPLACES)

        with (
            patch("copilotsetup.steps.shell_alias.IS_WINDOWS", False),
            patch("copilotsetup.steps.shell_alias._profile_paths_unix", return_value=[bashrc]),
        ):
            ShellAliasStep().run(ctx)

        content = bashrc.read_text("utf-8")

        # setdefault('marketplaces', {}).update(mkt)
        assert "setdefault('marketplaces', {}).update(mkt)" in content
        # config.get('marketplaces', {}).pop(mn, None)
        assert "config.get('marketplaces', {}).pop(mn, None)" in content
