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
        assert "⏳" in str(row[4])
        assert "↑ v2.0.0" in str(row[4])

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

        assert "⏳" not in str(row[4])
        assert "↑ v2.0.0" in str(row[4])

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

        assert "⏳" in str(row[4])
        assert "—" in str(row[4])


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
