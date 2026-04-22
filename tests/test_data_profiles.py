"""Tests for copilotsetup.data.profiles — profile directory scanning."""

from __future__ import annotations

import json
import os
from unittest.mock import patch

from copilotsetup.data.profiles import ProfileInfo, ProfileProvider


def test_empty_when_dir_missing(tmp_path):
    with patch.dict(os.environ, {"COPILOT_HOME": str(tmp_path)}):
        items = ProfileProvider().load()
    assert items == []


def test_reads_profiles_from_directory(tmp_path):
    prof_dir = tmp_path / "profiles"
    prof_dir.mkdir()
    (prof_dir / "work").mkdir()
    (prof_dir / "personal").mkdir()

    with patch.dict(os.environ, {"COPILOT_HOME": str(tmp_path)}):
        items = ProfileProvider().load()

    assert len(items) == 2
    names = [i.name for i in items]
    assert names == ["personal", "work"]


def test_active_profile_detected(tmp_path):
    prof_dir = tmp_path / "profiles"
    prof_dir.mkdir()
    (prof_dir / "work").mkdir()
    (prof_dir / "personal").mkdir()

    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"activeProfile": "work"}), encoding="utf-8")

    with patch.dict(os.environ, {"COPILOT_HOME": str(tmp_path)}):
        items = ProfileProvider().load()

    by_name = {i.name: i for i in items}
    assert by_name["work"].active is True
    assert by_name["personal"].active is False


def test_no_active_when_config_missing(tmp_path):
    prof_dir = tmp_path / "profiles"
    prof_dir.mkdir()
    (prof_dir / "default").mkdir()

    with patch.dict(os.environ, {"COPILOT_HOME": str(tmp_path)}):
        items = ProfileProvider().load()

    assert len(items) == 1
    assert items[0].active is False


def test_skips_files_in_profiles_dir(tmp_path):
    prof_dir = tmp_path / "profiles"
    prof_dir.mkdir()
    (prof_dir / "not-a-dir.txt").write_text("hi", encoding="utf-8")
    (prof_dir / "real-profile").mkdir()

    with patch.dict(os.environ, {"COPILOT_HOME": str(tmp_path)}):
        items = ProfileProvider().load()

    assert len(items) == 1
    assert items[0].name == "real-profile"


def test_items_are_frozen():
    info = ProfileInfo(name="test")
    try:
        info.name = "changed"  # type: ignore[misc]
        assert False, "Should have raised FrozenInstanceError"
    except AttributeError:
        pass


def test_path_is_populated(tmp_path):
    prof_dir = tmp_path / "profiles"
    prof_dir.mkdir()
    (prof_dir / "my-profile").mkdir()

    with patch.dict(os.environ, {"COPILOT_HOME": str(tmp_path)}):
        items = ProfileProvider().load()

    assert items[0].path == str(prof_dir / "my-profile")
