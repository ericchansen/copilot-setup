"""Tests for the PluginDisableStep."""

from __future__ import annotations

import json
from pathlib import Path

from copilotsetup.steps.plugin_disable import PluginDisableStep, _normalize, _under_prefix


class TestNormalize:
    def test_expands_home(self):
        result = _normalize("~/repos/agency-cowork")
        assert "~" not in result
        assert result.endswith("repos/agency-cowork")

    def test_strips_trailing_slash(self):
        result = _normalize("/tmp/foo/")
        assert not result.endswith("/")


class TestUnderPrefix:
    def test_exact_match(self):
        assert _under_prefix("C:/Users/me/repos/agency", "C:/Users/me/repos/agency")

    def test_child_path(self):
        assert _under_prefix("C:/Users/me/repos/agency/child", "C:/Users/me/repos/agency")

    def test_sibling_not_matched(self):
        assert not _under_prefix("C:/Users/me/repos/agency2", "C:/Users/me/repos/agency")

    def test_partial_name_not_matched(self):
        assert not _under_prefix("C:/Users/me/repos/agency-backup", "C:/Users/me/repos/agency")


class TestPluginDisableStep:
    def _make_ctx(
        self,
        tmp_path: Path,
        plugins: list[dict],
        disable_paths: list[str],
        source_plugins: list[dict] | None = None,
    ):
        """Create a minimal context with config.json and merged_config."""
        config_json = tmp_path / "config.json"
        config_json.write_text(json.dumps({"installed_plugins": plugins}, indent=2), "utf-8")

        class FakeMerged:
            def __init__(self):
                self.disable_plugin_paths = disable_paths
                self.plugins = {}
                self.source_plugins = source_plugins or []

        class FakeCtx:
            def __init__(self):
                self.config_json = config_json
                self.merged_config = FakeMerged()

        return FakeCtx()

    def test_disables_matching_plugins(self, tmp_path: Path):
        work_dir = tmp_path / "repos" / "agency-cowork" / "skills"
        plugins = [
            {"name": "calendar", "enabled": True, "cache_path": str(work_dir / "calendar")},
            {"name": "teams", "enabled": True, "cache_path": str(work_dir / "teams")},
            {"name": "microsoft-docs", "enabled": True, "cache_path": str(tmp_path / "other" / "docs")},
        ]
        ctx = self._make_ctx(tmp_path, plugins, [str(tmp_path / "repos" / "agency-cowork")])

        step = PluginDisableStep()
        result = step.run(ctx)

        # Read back config.json
        config = json.loads(ctx.config_json.read_text("utf-8"))
        by_name = {p["name"]: p for p in config["installed_plugins"]}

        assert by_name["calendar"]["enabled"] is False
        assert by_name["teams"]["enabled"] is False
        assert by_name["microsoft-docs"]["enabled"] is True  # not under the path

        # Check result items
        disabled_names = {i.name for i in result.items if i.status == "success"}
        assert disabled_names == {"calendar", "teams"}

    def test_already_disabled_not_touched(self, tmp_path: Path):
        work_dir = tmp_path / "repos" / "agency-cowork" / "skills"
        plugins = [
            {"name": "calendar", "enabled": False, "cache_path": str(work_dir / "calendar")},
        ]
        ctx = self._make_ctx(tmp_path, plugins, [str(tmp_path / "repos" / "agency-cowork")])

        step = PluginDisableStep()
        result = step.run(ctx)

        already = {i.name for i in result.items if i.status == "exists"}
        assert "calendar" in already

    def test_no_matching_plugins(self, tmp_path: Path):
        plugins = [
            {"name": "unrelated", "enabled": True, "cache_path": str(tmp_path / "elsewhere")},
        ]
        ctx = self._make_ctx(tmp_path, plugins, [str(tmp_path / "repos" / "agency-cowork")])

        step = PluginDisableStep()
        step.run(ctx)

        config = json.loads(ctx.config_json.read_text("utf-8"))
        assert config["installed_plugins"][0]["enabled"] is True

    def test_check_returns_false_without_paths(self, tmp_path: Path):
        ctx = self._make_ctx(tmp_path, [], [], source_plugins=[])
        step = PluginDisableStep()
        assert step.check(ctx) is False

    def test_check_returns_true_with_paths(self, tmp_path: Path):
        ctx = self._make_ctx(tmp_path, [], ["~/repos/agency-cowork"])
        step = PluginDisableStep()
        assert step.check(ctx) is True

    def test_check_returns_true_with_source_plugins(self, tmp_path: Path):
        ctx = self._make_ctx(
            tmp_path,
            [],
            [],
            source_plugins=[{"name": "my-plugin", "alias": "", "path": "/tmp"}],
        )
        step = PluginDisableStep()
        assert step.check(ctx) is True

    def test_stores_disabled_names_on_context(self, tmp_path: Path):
        work_dir = tmp_path / "repos" / "agency-cowork" / "skills"
        plugins = [
            {"name": "calendar", "enabled": True, "cache_path": str(work_dir / "calendar")},
            {"name": "teams", "enabled": False, "cache_path": str(work_dir / "teams")},
        ]
        ctx = self._make_ctx(tmp_path, plugins, [str(tmp_path / "repos" / "agency-cowork")])

        step = PluginDisableStep()
        step.run(ctx)

        assert ctx.disabled_plugin_names == {"calendar", "teams"}

    def test_source_plugin_registered_new(self, tmp_path: Path):
        """Source-as-plugin creates a new installed_plugins entry."""
        plugin_dir = tmp_path / "copilot-config-work" / ".copilot"
        plugin_dir.mkdir(parents=True)
        ctx = self._make_ctx(
            tmp_path,
            [],
            [],
            source_plugins=[
                {"name": "copilot-config-work", "alias": "copilot-work", "path": str(plugin_dir)},
            ],
        )

        step = PluginDisableStep()
        step.run(ctx)

        config = json.loads(ctx.config_json.read_text("utf-8"))
        by_name = {p["name"]: p for p in config["installed_plugins"]}
        assert "copilot-config-work" in by_name
        assert by_name["copilot-config-work"]["enabled"] is False  # has alias
        assert by_name["copilot-config-work"]["cache_path"] == str(plugin_dir)

    def test_source_plugin_no_alias_enabled(self, tmp_path: Path):
        """Source-as-plugin without alias is always enabled."""
        plugin_dir = tmp_path / "copilot-config" / ".copilot"
        plugin_dir.mkdir(parents=True)
        ctx = self._make_ctx(
            tmp_path,
            [],
            [],
            source_plugins=[
                {"name": "copilot-config", "alias": "", "path": str(plugin_dir)},
            ],
        )

        step = PluginDisableStep()
        step.run(ctx)

        config = json.loads(ctx.config_json.read_text("utf-8"))
        by_name = {p["name"]: p for p in config["installed_plugins"]}
        assert "copilot-config" in by_name
        assert by_name["copilot-config"]["enabled"] is True

    def test_source_plugin_already_registered_updated(self, tmp_path: Path):
        """Existing entry gets updated path and enabled state."""
        old_dir = tmp_path / "old-path"
        new_dir = tmp_path / "new-path"
        new_dir.mkdir(parents=True)
        plugins = [
            {"name": "copilot-config-work", "enabled": True, "cache_path": str(old_dir)},
        ]
        ctx = self._make_ctx(
            tmp_path,
            plugins,
            [],
            source_plugins=[
                {"name": "copilot-config-work", "alias": "copilot-work", "path": str(new_dir)},
            ],
        )

        step = PluginDisableStep()
        step.run(ctx)

        config = json.loads(ctx.config_json.read_text("utf-8"))
        by_name = {p["name"]: p for p in config["installed_plugins"]}
        assert by_name["copilot-config-work"]["cache_path"] == str(new_dir)
        assert by_name["copilot-config-work"]["enabled"] is False

    def test_source_plugin_alias_in_disabled_names(self, tmp_path: Path):
        """Source plugins with alias should appear in disabled_plugin_names."""
        plugin_dir = tmp_path / ".copilot"
        plugin_dir.mkdir(parents=True)
        ctx = self._make_ctx(
            tmp_path,
            [],
            [],
            source_plugins=[
                {"name": "copilot-config-work", "alias": "copilot-work", "path": str(plugin_dir)},
            ],
        )

        step = PluginDisableStep()
        step.run(ctx)

        assert "copilot-config-work" in ctx.disabled_plugin_names
