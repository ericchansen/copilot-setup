"""Tests for copilotsetup.utils.file_io — atomic JSON read/write."""

from __future__ import annotations

import json

from copilotsetup.utils.file_io import read_json, write_json


def test_read_json_valid(tmp_path):
    p = tmp_path / "test.json"
    p.write_text('{"key": "value"}', encoding="utf-8")
    assert read_json(p) == {"key": "value"}


def test_read_json_missing(tmp_path):
    p = tmp_path / "nope.json"
    assert read_json(p) is None


def test_read_json_malformed(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{broken", encoding="utf-8")
    assert read_json(p) is None


def test_write_json_creates_file(tmp_path):
    p = tmp_path / "out.json"
    write_json(p, {"a": 1})
    assert p.exists()
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data == {"a": 1}


def test_write_json_creates_backup(tmp_path):
    p = tmp_path / "out.json"
    write_json(p, {"v": 1})
    write_json(p, {"v": 2})
    bak = tmp_path / "out.json.bak"
    assert bak.exists()
    assert json.loads(bak.read_text(encoding="utf-8")) == {"v": 1}
    assert json.loads(p.read_text(encoding="utf-8")) == {"v": 2}


def test_write_json_creates_parent_dirs(tmp_path):
    p = tmp_path / "sub" / "dir" / "out.json"
    write_json(p, [1, 2, 3])
    assert p.exists()
    assert read_json(p) == [1, 2, 3]


def test_roundtrip(tmp_path):
    p = tmp_path / "rt.json"
    data = {"servers": [{"name": "a"}, {"name": "b"}], "count": 2}
    write_json(p, data)
    assert read_json(p) == data


# --- JSONC (JSON with Comments) support ---


def test_read_json_strips_leading_line_comments(tmp_path):
    p = tmp_path / "commented.json"
    p.write_text(
        '// This is a comment\n// Another comment\n{"key": "value"}\n',
        encoding="utf-8",
    )
    assert read_json(p) == {"key": "value"}


def test_read_json_strips_indented_comments(tmp_path):
    p = tmp_path / "indented.json"
    p.write_text(
        '{\n  // inline section comment\n  "a": 1\n}\n',
        encoding="utf-8",
    )
    assert read_json(p) == {"a": 1}


def test_read_json_preserves_slashes_in_values(tmp_path):
    """Ensure // inside JSON string values is not stripped."""
    p = tmp_path / "url.json"
    p.write_text('{"url": "https://example.com"}', encoding="utf-8")
    assert read_json(p) == {"url": "https://example.com"}
