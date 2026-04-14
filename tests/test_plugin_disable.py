"""Tests for the PluginRegisterStep."""

from __future__ import annotations

import json
from pathlib import Path

from copilotsetup.steps.plugin_disable import PluginRegisterStep


class TestPluginRegisterStep:
    def _make_ctx(
        self,
        tmp_path: Path,
        plugins: list[dict],
        source_plugins: list[dict] | None = None,
    ):
        """Create a minimal context with config.json and merged_config."""
        config_json = tmp_path / "config.json"
        config_json.write_text(json.dumps({"installed_plugins": plugins}, indent=2), "utf-8")

        class FakeMerged:
            def __init__(self):
                self.plugins = {}
                self.source_plugins = source_plugins or []

        class FakeCtx:
            def __init__(self):
                self.config_json = config_json
                self.merged_config = FakeMerged()

        return FakeCtx()

    def test_check_returns_false_without_source_plugins(self, tmp_path: Path):
        ctx = self._make_ctx(tmp_path, [], source_plugins=[])
        step = PluginRegisterStep()
        assert step.check(ctx) is False

    def test_check_returns_true_with_source_plugins(self, tmp_path: Path):
        ctx = self._make_ctx(
            tmp_path,
            [],
            source_plugins=[{"name": "my-plugin", "path": "/tmp"}],
        )
        step = PluginRegisterStep()
        assert step.check(ctx) is True

    def test_source_plugin_registered_new(self, tmp_path: Path):
        """Source-as-plugin creates a new installed_plugins entry, always enabled."""
        plugin_dir = tmp_path / "copilot-config-work" / ".copilot"
        plugin_dir.mkdir(parents=True)
        ctx = self._make_ctx(
            tmp_path,
            [],
            source_plugins=[
                {"name": "copilot-config-work", "path": str(plugin_dir)},
            ],
        )

        step = PluginRegisterStep()
        step.run(ctx)

        config = json.loads(ctx.config_json.read_text("utf-8"))
        by_name = {p["name"]: p for p in config["installed_plugins"]}
        assert "copilot-config-work" in by_name
        assert by_name["copilot-config-work"]["enabled"] is True
        assert by_name["copilot-config-work"]["cache_path"] == str(plugin_dir)

    def test_source_plugin_enabled(self, tmp_path: Path):
        """Source-as-plugin is always enabled."""
        plugin_dir = tmp_path / "copilot-config" / ".copilot"
        plugin_dir.mkdir(parents=True)
        ctx = self._make_ctx(
            tmp_path,
            [],
            source_plugins=[
                {"name": "copilot-config", "path": str(plugin_dir)},
            ],
        )

        step = PluginRegisterStep()
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
            {"name": "copilot-config-work", "enabled": False, "cache_path": str(old_dir)},
        ]
        ctx = self._make_ctx(
            tmp_path,
            plugins,
            source_plugins=[
                {"name": "copilot-config-work", "path": str(new_dir)},
            ],
        )

        step = PluginRegisterStep()
        step.run(ctx)

        config = json.loads(ctx.config_json.read_text("utf-8"))
        by_name = {p["name"]: p for p in config["installed_plugins"]}
        assert by_name["copilot-config-work"]["cache_path"] == str(new_dir)
        assert by_name["copilot-config-work"]["enabled"] is True
