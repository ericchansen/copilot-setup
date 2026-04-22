"""Tests for copilotsetup.data.extensions — extension directory scanning."""

from __future__ import annotations

import json
import os
from unittest.mock import patch

from copilotsetup.data.extensions import ExtensionInfo, ExtensionProvider


def test_empty_when_dir_missing(tmp_path):
    with patch.dict(os.environ, {"COPILOT_HOME": str(tmp_path)}):
        items = ExtensionProvider().load()
    assert items == []


def test_reads_extensions_from_directory(tmp_path):
    ext_dir = tmp_path / "extensions"
    ext_dir.mkdir()
    (ext_dir / "ext-a").mkdir()
    (ext_dir / "ext-b").mkdir()
    pkg = ext_dir / "ext-b" / "package.json"
    pkg.write_text(json.dumps({"version": "1.2.3"}), encoding="utf-8")

    with patch.dict(os.environ, {"COPILOT_HOME": str(tmp_path)}):
        items = ExtensionProvider().load()

    assert len(items) == 2
    names = [i.name for i in items]
    assert names == ["ext-a", "ext-b"]

    by_name = {i.name: i for i in items}
    assert by_name["ext-b"].version == "1.2.3"
    assert by_name["ext-a"].version == ""


def test_skips_files_in_extensions_dir(tmp_path):
    ext_dir = tmp_path / "extensions"
    ext_dir.mkdir()
    (ext_dir / "not-a-dir.txt").write_text("hi", encoding="utf-8")
    (ext_dir / "real-ext").mkdir()

    with patch.dict(os.environ, {"COPILOT_HOME": str(tmp_path)}):
        items = ExtensionProvider().load()

    assert len(items) == 1
    assert items[0].name == "real-ext"


def test_handles_malformed_package_json(tmp_path):
    ext_dir = tmp_path / "extensions"
    ext_dir.mkdir()
    bad = ext_dir / "bad-ext"
    bad.mkdir()
    (bad / "package.json").write_text("{not valid json", encoding="utf-8")

    with patch.dict(os.environ, {"COPILOT_HOME": str(tmp_path)}):
        items = ExtensionProvider().load()

    assert len(items) == 1
    assert items[0].version == ""


def test_items_are_frozen():
    info = ExtensionInfo(name="test")
    try:
        info.name = "changed"  # type: ignore[misc]
        assert False, "Should have raised FrozenInstanceError"
    except AttributeError:
        pass


def test_path_is_populated(tmp_path):
    ext_dir = tmp_path / "extensions"
    ext_dir.mkdir()
    (ext_dir / "my-ext").mkdir()

    with patch.dict(os.environ, {"COPILOT_HOME": str(tmp_path)}):
        items = ExtensionProvider().load()

    assert items[0].path == str(ext_dir / "my-ext")
