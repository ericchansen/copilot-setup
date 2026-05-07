"""Tests for PluginsTab upgrade detection — two-phase loading and generation guard."""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import MagicMock

from copilotsetup.data.plugins import PluginInfo
from copilotsetup.plugin_upgrades import STATUS_UPGRADABLE, PluginUpgradeInfo


def _make_plugin(name: str = "test-plugin", **kwargs) -> PluginInfo:
    defaults = {
        "name": name,
        "source": "test",
        "version": "1.0.0",
        "installed": True,
        "install_path": "/fake/path",
    }
    defaults.update(kwargs)
    return PluginInfo(**defaults)


class TestApplyUpgrades:
    """Tests for _apply_upgrades generation guard and provisional flag."""

    def _make_tab(self, items: list[PluginInfo]) -> MagicMock:
        """Create a mock PluginsTab with just enough state for _apply_upgrades."""
        from copilotsetup.tabs.plugins import PluginsTab

        tab = MagicMock(spec=PluginsTab)
        tab._items = list(items)
        tab._active_gen = 1
        tab._apply_filter = MagicMock()
        # Bind the real method
        tab._apply_upgrades = PluginsTab._apply_upgrades.__get__(tab, PluginsTab)
        return tab

    def test_apply_upgrades_sets_provisional_flag(self):
        """Provisional results should set upgrade_provisional=True."""
        item = _make_plugin()
        tab = self._make_tab([item])
        result_map = {
            "test-plugin": PluginUpgradeInfo(
                name="test-plugin",
                path=None,
                status=STATUS_UPGRADABLE,
                latest_version="v2.0.0",
            ),
        }

        tab._apply_upgrades(result_map, gen=1, provisional=True)

        updated = tab._items[0]
        assert updated.upgrade_available is True
        assert updated.upgrade_version == "v2.0.0"
        assert updated.upgrade_provisional is True

    def test_apply_upgrades_clears_provisional_on_fresh(self):
        """Fresh (non-provisional) results should clear upgrade_provisional."""
        item = _make_plugin(upgrade_provisional=True, upgrade_available=True)
        tab = self._make_tab([item])
        result_map = {
            "test-plugin": PluginUpgradeInfo(
                name="test-plugin",
                path=None,
                status=STATUS_UPGRADABLE,
                latest_version="v3.0.0",
            ),
        }

        tab._apply_upgrades(result_map, gen=1, provisional=False)

        updated = tab._items[0]
        assert updated.upgrade_available is True
        assert updated.upgrade_version == "v3.0.0"
        assert updated.upgrade_provisional is False

    def test_apply_upgrades_discards_stale_generation(self):
        """Results from an old generation should be silently discarded."""
        item = _make_plugin()
        tab = self._make_tab([item])
        tab._active_gen = 5  # current generation is 5

        result_map = {
            "test-plugin": PluginUpgradeInfo(
                name="test-plugin",
                path=None,
                status=STATUS_UPGRADABLE,
                latest_version="v2.0.0",
            ),
        }

        tab._apply_upgrades(result_map, gen=3, provisional=False)

        # Items should be unchanged — stale result discarded
        assert tab._items[0].upgrade_available is False
        tab._apply_filter.assert_not_called()

    def test_apply_upgrades_no_upgrade_preserves_provisional(self):
        """When no upgrade is available, provisional flag should still propagate."""
        item = _make_plugin()
        tab = self._make_tab([item])
        result_map = {
            "test-plugin": PluginUpgradeInfo(
                name="test-plugin",
                path=None,
                status="up-to-date",
            ),
        }

        tab._apply_upgrades(result_map, gen=1, provisional=True)

        updated = tab._items[0]
        assert updated.upgrade_summary == "—"
        assert updated.upgrade_provisional is True

    def test_apply_upgrades_no_upgrade_clears_provisional_on_fresh(self):
        """Fresh 'no upgrade' results should clear provisional flag."""
        item = _make_plugin(upgrade_provisional=True)
        tab = self._make_tab([item])
        result_map = {
            "test-plugin": PluginUpgradeInfo(
                name="test-plugin",
                path=None,
                status="up-to-date",
            ),
        }

        tab._apply_upgrades(result_map, gen=1, provisional=False)

        updated = tab._items[0]
        assert updated.upgrade_summary == "—"
        assert updated.upgrade_provisional is False


class TestRowForProvisional:
    """Tests for provisional indicator in row_for output."""

    def test_row_shows_hourglass_for_provisional(self):
        """Provisional upgrade results should show ⏳ suffix."""
        from copilotsetup.tabs.plugins import PluginsTab

        item = _make_plugin(
            upgrade_available=True,
            upgrade_summary="↑ v2.0.0",
            upgrade_provisional=True,
        )

        tab = MagicMock(spec=PluginsTab)
        tab.row_for = PluginsTab.row_for.__get__(tab, PluginsTab)
        row = tab.row_for(item)

        # Upgrade column is index 4
        assert "⏳" in str(row[6])
        assert "↑ v2.0.0" in str(row[6])

    def test_row_no_hourglass_for_fresh(self):
        """Fresh (non-provisional) results should not show ⏳."""
        from copilotsetup.tabs.plugins import PluginsTab

        item = _make_plugin(
            upgrade_available=True,
            upgrade_summary="↑ v2.0.0",
            upgrade_provisional=False,
        )

        tab = MagicMock(spec=PluginsTab)
        tab.row_for = PluginsTab.row_for.__get__(tab, PluginsTab)
        row = tab.row_for(item)

        assert "⏳" not in str(row[6])
        assert "↑ v2.0.0" in str(row[6])

    def test_row_shows_hourglass_for_provisional_no_upgrade(self):
        """Provisional 'no upgrade' should also show ⏳ suffix."""
        from copilotsetup.tabs.plugins import PluginsTab

        item = _make_plugin(
            upgrade_summary="—",
            upgrade_provisional=True,
        )

        tab = MagicMock(spec=PluginsTab)
        tab.row_for = PluginsTab.row_for.__get__(tab, PluginsTab)
        row = tab.row_for(item)

        assert "⏳" in str(row[6])
        assert "—" in str(row[6])


class TestPluginInfoProvisionalField:
    """Tests for the upgrade_provisional field on PluginInfo."""

    def test_default_provisional_is_false(self):
        item = _make_plugin()
        assert item.upgrade_provisional is False

    def test_provisional_can_be_set(self):
        item = _make_plugin(upgrade_provisional=True)
        assert item.upgrade_provisional is True

    def test_replace_preserves_provisional(self):
        item = _make_plugin(upgrade_provisional=True)
        updated = replace(item, upgrade_summary="↑ v2.0.0")
        assert updated.upgrade_provisional is True


class TestDevState:
    """Tests for local-dev install rendering and behavior."""

    def _make_tab(self, items: list[PluginInfo]) -> MagicMock:
        from copilotsetup.tabs.plugins import PluginsTab

        tab = MagicMock(spec=PluginsTab)
        tab._items = list(items)
        tab._active_gen = 1
        tab._apply_filter = MagicMock()
        tab._apply_upgrades = PluginsTab._apply_upgrades.__get__(tab, PluginsTab)
        return tab

    def test_apply_upgrades_propagates_dev_fields(self):
        """Dev-state results populate dev_summary, dev_branch, dev_commits_ahead, latest_release."""
        from copilotsetup.plugin_upgrades import STATUS_LOCAL_DEV

        item = _make_plugin()
        tab = self._make_tab([item])
        result_map = {
            "test-plugin": PluginUpgradeInfo(
                name="test-plugin",
                path=None,
                status=STATUS_LOCAL_DEV,
                dev_branch="feat/gh-writer",
                dev_commits_ahead=4,
                current_version="v1.1.0",
                latest_version="v2.0.2",
            ),
        }

        tab._apply_upgrades(result_map, gen=1, provisional=False)

        updated = tab._items[0]
        assert updated.upgrade_available is False
        assert updated.upgrade_summary == ""
        assert updated.dev_summary == "dev: feat/gh-writer"
        assert updated.dev_branch == "feat/gh-writer"
        assert updated.dev_commits_ahead == 4
        assert updated.latest_release == "v2.0.2"

    def test_apply_upgrades_clears_dev_when_pinning_to_tag(self):
        """If a previously-dev item now reports STATUS_UPGRADABLE, clear dev fields."""
        item = _make_plugin(
            dev_summary="dev: feat/gh-writer",
            dev_branch="feat/gh-writer",
            dev_commits_ahead=4,
        )
        tab = self._make_tab([item])
        result_map = {
            "test-plugin": PluginUpgradeInfo(
                name="test-plugin",
                path=None,
                status="upgradable",
                latest_version="v2.0.2",
            ),
        }

        tab._apply_upgrades(result_map, gen=1, provisional=False)

        updated = tab._items[0]
        assert updated.upgrade_available is True
        assert updated.dev_summary == ""
        assert updated.dev_branch == ""
        assert updated.dev_commits_ahead == 0

    def test_row_shows_dev_summary_in_upgrade_column(self):
        """Dev installs show 'dev: <branch>' in the Upgrade column instead of an arrow."""
        from copilotsetup.tabs.plugins import PluginsTab

        item = _make_plugin(
            upgrade_summary="",
            dev_summary="dev: feat/gh-writer",
            dev_branch="feat/gh-writer",
        )

        tab = MagicMock(spec=PluginsTab)
        tab.row_for = PluginsTab.row_for.__get__(tab, PluginsTab)
        row = tab.row_for(item)

        assert "dev: feat/gh-writer" in str(row[6])
        assert "↑" not in str(row[6])

    def test_row_shows_hourglass_for_provisional_dev(self):
        """Provisional dev results also get the ⏳ marker."""
        from copilotsetup.tabs.plugins import PluginsTab

        item = _make_plugin(
            upgrade_summary="",
            dev_summary="dev: main",
            dev_branch="main",
            upgrade_provisional=True,
        )

        tab = MagicMock(spec=PluginsTab)
        tab.row_for = PluginsTab.row_for.__get__(tab, PluginsTab)
        row = tab.row_for(item)

        assert "dev: main" in str(row[6])
        assert "⏳" in str(row[6])

    def test_handle_upgrade_short_circuits_for_dev_install(self):
        """Pressing 'u' on a dev install must NOT call copilot CLI."""
        from copilotsetup.tabs.plugins import PluginsTab

        item = _make_plugin(
            dev_summary="dev: feat/gh-writer",
            dev_branch="feat/gh-writer",
            latest_release="v2.0.2",
            marketplace="github",
        )

        tab = MagicMock(spec=PluginsTab)
        tab.get_selected_item = MagicMock(return_value=item)
        tab.notify = MagicMock()
        tab.refresh_data = MagicMock()
        tab.handle_upgrade = PluginsTab.handle_upgrade.__get__(tab, PluginsTab)

        from unittest.mock import patch as _patch

        with _patch("copilotsetup.tabs.plugins.run_copilot") as mock_run:
            tab.handle_upgrade()

        mock_run.assert_not_called()
        tab.refresh_data.assert_not_called()
        # Notification mentions branch and the suggested git command.
        assert tab.notify.called
        call_args = tab.notify.call_args
        msg = call_args[0][0]
        assert "feat/gh-writer" in msg
        assert "git checkout v2.0.2" in msg
        assert "copilot plugin install" in msg
        assert "copilot plugin install ." not in msg  # bare dot is invalid
        assert "test-plugin@github" in msg  # should use name@marketplace form

    def test_handle_upgrade_normal_path_unchanged(self):
        """Non-dev plugins with upgrade_available still call the CLI."""
        from copilotsetup.tabs.plugins import PluginsTab

        item = _make_plugin(
            upgrade_available=True,
            upgrade_summary="↑ v2.0.0",
            upgrade_version="v2.0.0",
        )

        tab = MagicMock(spec=PluginsTab)
        tab.get_selected_item = MagicMock(return_value=item)
        tab.notify = MagicMock()
        tab.refresh_data = MagicMock()
        tab.handle_upgrade = PluginsTab.handle_upgrade.__get__(tab, PluginsTab)

        from unittest.mock import patch as _patch

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "ok"
        mock_result.stderr = ""

        with (
            _patch("copilotsetup.tabs.plugins.run_copilot", return_value=mock_result) as mock_run,
            _patch("copilotsetup.upgrade_cache.UpgradeCache.get_instance"),
        ):
            tab.handle_upgrade()

        mock_run.assert_called_once()
        assert mock_run.call_args[0][:3] == ("plugin", "update", "test-plugin")

    def test_apply_upgrades_clears_stale_upgrade_state_on_no_upgrade(self):
        """Regression: a fresh ``no-upgrade`` result must clear stale upgrade_available.

        Previously, the fallback branch in ``_apply_upgrades`` only updated
        ``upgrade_summary='—'`` but left ``upgrade_available=True`` and
        ``upgrade_version='v2.0.0'`` from a stale provisional pass. That made
        ``[u]`` still trigger ``run_copilot`` even though the row showed no
        upgrade available.
        """
        from copilotsetup.plugin_upgrades import STATUS_UP_TO_DATE

        # Stale provisional state: upgrade was previously available.
        item = _make_plugin(
            upgrade_available=True,
            upgrade_summary="↑ v2.0.0",
            upgrade_version="v2.0.0",
            upgrade_provisional=True,
        )
        tab = self._make_tab([item])
        # Fresh result says we're up to date — no upgrade.
        result_map = {
            "test-plugin": PluginUpgradeInfo(
                name="test-plugin",
                path=None,
                status=STATUS_UP_TO_DATE,
                latest_version="v1.0.0",
            ),
        }

        tab._apply_upgrades(result_map, gen=1, provisional=False)

        updated = tab._items[0]
        assert updated.upgrade_summary == "—"
        assert updated.upgrade_available is False, "stale upgrade_available must be cleared so [u] does not trigger CLI"
        assert updated.upgrade_version == "", "stale upgrade_version must be cleared"
        assert updated.upgrade_provisional is False

    def test_detail_shows_commits_past_tag_for_dev_install(self):
        """Detail pane renders the 'N commit(s) past last ancestor tag' line for dev installs.

        Regression: the gate previously required ``upgrade_version`` to be
        truthy, but dev installs intentionally clear that field, so the line
        was never rendered in practice.
        """
        from copilotsetup.tabs.plugins import PluginsTab

        item = _make_plugin(
            upgrade_summary="",
            upgrade_version="",  # cleared by dev path
            dev_summary="dev: feat/gh-writer",
            dev_branch="feat/gh-writer",
            dev_commits_ahead=4,
            latest_release="v2.0.2",
        )

        tab = MagicMock(spec=PluginsTab)
        tab.detail_for = PluginsTab.detail_for.__get__(tab, PluginsTab)
        detail = tab.detail_for(item)

        assert "4 commit(s) past last ancestor tag" in detail
        assert "Latest release on origin" in detail
        assert "v2.0.2" in detail
