"""Tests for copilotsetup.upgrade_cache — disk-backed upgrade result cache."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from copilotsetup.plugin_upgrades import PluginUpgradeInfo
from copilotsetup.upgrade_cache import _SCHEMA_VERSION, _TTL, UpgradeCache


def test_get_returns_none_when_empty(tmp_path):
    cache = UpgradeCache(path=tmp_path / "cache.json")
    assert cache.get("nonexistent") is None


def test_set_and_get_round_trip(tmp_path):
    cache = UpgradeCache(path=tmp_path / "cache.json")
    cache.set("my-plugin", "v2.0.0")
    assert cache.get("my-plugin") == "v2.0.0"


def test_get_returns_none_after_ttl_expires(tmp_path):
    cache_path = tmp_path / "cache.json"
    # Write a cache entry with an old timestamp
    old_time = (datetime.now(timezone.utc) - _TTL - timedelta(hours=1)).isoformat()
    cache_path.write_text(
        json.dumps(
            {
                "_version": _SCHEMA_VERSION,
                "plugins": {
                    "old-plugin": {
                        "latest_version": "v1.0.0",
                        "checked_at": old_time,
                    }
                },
            }
        )
    )
    cache = UpgradeCache(path=cache_path)
    assert cache.get("old-plugin") is None  # expired


def test_get_returns_value_within_ttl(tmp_path):
    cache_path = tmp_path / "cache.json"
    recent_time = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    cache_path.write_text(
        json.dumps(
            {
                "_version": _SCHEMA_VERSION,
                "plugins": {
                    "fresh-plugin": {
                        "latest_version": "v3.0.0",
                        "checked_at": recent_time,
                    }
                },
            }
        )
    )
    cache = UpgradeCache(path=cache_path)
    assert cache.get("fresh-plugin") == "v3.0.0"


def test_invalidate_removes_entry(tmp_path):
    cache = UpgradeCache(path=tmp_path / "cache.json")
    cache.set("to-remove", "v1.0.0")
    assert cache.get("to-remove") == "v1.0.0"
    cache.invalidate("to-remove")
    assert cache.get("to-remove") is None


def test_invalidate_nonexistent_is_noop(tmp_path):
    cache = UpgradeCache(path=tmp_path / "cache.json")
    cache.invalidate("ghost")  # should not raise


def test_corrupted_cache_file_resets(tmp_path):
    cache_path = tmp_path / "cache.json"
    cache_path.write_text("not valid json {{{")
    cache = UpgradeCache(path=cache_path)
    assert cache.get("anything") is None
    cache.set("new", "v1.0.0")
    assert cache.get("new") == "v1.0.0"


def test_wrong_schema_version_resets(tmp_path):
    cache_path = tmp_path / "cache.json"
    cache_path.write_text(
        json.dumps(
            {
                "_version": 999,
                "plugins": {
                    "old": {
                        "latest_version": "v1.0.0",
                        "checked_at": datetime.now(timezone.utc).isoformat(),
                    }
                },
            }
        )
    )
    cache = UpgradeCache(path=cache_path)
    assert cache.get("old") is None  # discarded


def test_missing_cache_file_starts_fresh(tmp_path):
    cache = UpgradeCache(path=tmp_path / "nonexistent" / "cache.json")
    assert cache.get("anything") is None
    # set should not crash even if parent dir doesn't exist
    # (write_json creates parents)
    cache.set("new", "v1.0.0")


def test_multiple_plugins_independent(tmp_path):
    cache = UpgradeCache(path=tmp_path / "cache.json")
    cache.set("plugin-a", "v1.0.0")
    cache.set("plugin-b", "v2.0.0")
    assert cache.get("plugin-a") == "v1.0.0"
    assert cache.get("plugin-b") == "v2.0.0"
    cache.invalidate("plugin-a")
    assert cache.get("plugin-a") is None
    assert cache.get("plugin-b") == "v2.0.0"


def test_get_or_check_cache_hit_does_not_refresh_timestamp(tmp_path):
    """Cache hit should NOT refresh checked_at — TTL should eventually expire."""
    import time

    cache = UpgradeCache(path=tmp_path / "cache.json")
    cache.set("my-plugin", "v2.0.0")

    raw = json.loads((tmp_path / "cache.json").read_text(encoding="utf-8"))
    original_checked_at = raw["plugins"]["my-plugin"]["checked_at"]

    time.sleep(0.1)

    with patch("copilotsetup.upgrade_cache.check_plugin") as mock_check:
        mock_check.return_value = PluginUpgradeInfo(
            name="my-plugin",
            path=None,
            status="up-to-date",
            current_version="v1.0.0",
            latest_version="v2.0.0",
            network_verified=True,
        )
        cache.get_or_check("my-plugin", "/fake/path", "1.0.0")

    raw2 = json.loads((tmp_path / "cache.json").read_text(encoding="utf-8"))
    assert raw2["plugins"]["my-plugin"]["checked_at"] == original_checked_at


def test_get_or_check_skips_unverified_up_to_date_cache_write(tmp_path):
    """Up-to-date results from local fallback should not populate the cache."""
    cache_path = tmp_path / "cache.json"
    cache = UpgradeCache(path=cache_path)

    with patch("copilotsetup.upgrade_cache.check_plugin") as mock_check:
        mock_check.return_value = PluginUpgradeInfo(
            name="my-plugin",
            path=None,
            status="up-to-date",
            current_version="v1.0.0",
            network_verified=False,
        )
        cache.get_or_check("my-plugin", "/fake/path", "1.0.0")

    assert not cache_path.exists()


def test_singleton_returns_same_instance():
    """get_instance() should return the same object."""
    UpgradeCache._instance = None
    try:
        a = UpgradeCache.get_instance()
        b = UpgradeCache.get_instance()
        assert a is b
    finally:
        UpgradeCache._instance = None
