"""Tests for copilotsetup.data.hooks — hook config loading."""

from __future__ import annotations

import json

from copilotsetup.data.hooks import HookInfo, HookProvider


def test_returns_empty_when_config_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    assert HookProvider().load() == []


def test_returns_empty_when_hooks_key_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    (tmp_path / "config.json").write_text(json.dumps({"other": 1}))
    assert HookProvider().load() == []


def test_loads_hooks_from_config(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    cfg = {
        "hooks": {
            "onStart": [{"command": "echo hello"}],
            "onStop": [{"command": "echo bye"}, {"command": "cleanup.sh"}],
        }
    }
    (tmp_path / "config.json").write_text(json.dumps(cfg))
    items = HookProvider().load()
    assert len(items) == 3
    events = [i.event for i in items]
    assert events.count("onStart") == 1
    assert events.count("onStop") == 2


def test_skips_entries_without_command(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    cfg = {"hooks": {"onStart": [{"command": ""}, {"not_command": "x"}]}}
    (tmp_path / "config.json").write_text(json.dumps(cfg))
    assert HookProvider().load() == []


def test_skips_non_dict_entries(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    cfg = {"hooks": {"onStart": ["just-a-string", 42, None]}}
    (tmp_path / "config.json").write_text(json.dumps(cfg))
    assert HookProvider().load() == []


def test_skips_non_list_hook_values(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    cfg = {"hooks": {"onStart": "not-a-list"}}
    (tmp_path / "config.json").write_text(json.dumps(cfg))
    assert HookProvider().load() == []


def test_items_are_frozen():
    info = HookInfo(event="onStart", command="echo hi")
    try:
        info.event = "changed"  # type: ignore[misc]
        raise AssertionError("Should have raised FrozenInstanceError")
    except AttributeError:
        pass


def test_default_hook_type():
    info = HookInfo(event="e", command="c")
    assert info.hook_type == "command"
