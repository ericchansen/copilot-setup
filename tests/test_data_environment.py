"""Tests for copilotsetup.data.environment — env var scanning."""

from __future__ import annotations

import os
from unittest.mock import patch

from copilotsetup.data.environment import EnvironmentProvider, EnvVarInfo


def test_loads_copilot_prefixed_vars():
    env = {"COPILOT_FOO": "bar", "OTHER_VAR": "nope"}
    with patch.dict(os.environ, env, clear=True):
        items = EnvironmentProvider().load()
    names = [i.name for i in items]
    assert "COPILOT_FOO" in names
    assert "OTHER_VAR" not in names


def test_sensitive_vars_are_masked():
    env = {"COPILOT_AUTH_TOKEN": "super-secret-value-12345"}
    with patch.dict(os.environ, env, clear=True):
        items = EnvironmentProvider().load()
    assert len(items) == 1
    item = items[0]
    assert item.is_sensitive
    assert "super-secret-value-12345" not in item.value
    assert "****" in item.value or "…" in item.value


def test_non_sensitive_vars_show_full_value():
    env = {"GH_EDITOR": "vim"}
    with patch.dict(os.environ, env, clear=True):
        items = EnvironmentProvider().load()
    assert len(items) == 1
    assert items[0].value == "vim"
    assert not items[0].is_sensitive


def test_empty_env_returns_empty():
    with patch.dict(os.environ, {}, clear=True):
        items = EnvironmentProvider().load()
    assert items == []


def test_items_are_frozen():
    info = EnvVarInfo(name="A", value="B")
    try:
        info.name = "C"  # type: ignore[misc]
        assert False, "Should have raised FrozenInstanceError"
    except AttributeError:
        pass


def test_multiple_prefixes():
    env = {
        "COPILOT_A": "1",
        "GITHUB_B": "2",
        "HTTP_PROXY": "http://proxy",
        "RANDOM": "skip",
    }
    with patch.dict(os.environ, env, clear=True):
        items = EnvironmentProvider().load()
    names = {i.name for i in items}
    assert names == {"COPILOT_A", "GITHUB_B", "HTTP_PROXY"}
