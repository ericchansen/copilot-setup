"""Tests for the doctor module — MCP server health probes."""

from __future__ import annotations

import http.server
import socketserver
import sys
import textwrap
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

from copilotsetup.doctor import (
    DEFAULT_TIMEOUT,
    HealthInfo,
    probe_all,
    probe_http,
    probe_server_entry,
    probe_stdio,
)

# -- stdio tests --------------------------------------------------------------


def _write_stdio_server(tmp_path: Path, body: str) -> Path:
    """Write a minimal Python script that reads one line and writes one line."""
    script = tmp_path / "fake_server.py"
    script.write_text(textwrap.dedent(body), "utf-8")
    return script


def test_probe_stdio_ok(tmp_path: Path) -> None:
    script = _write_stdio_server(
        tmp_path,
        """
        import json, sys
        line = sys.stdin.readline()
        req = json.loads(line)
        resp = {
            "jsonrpc": "2.0",
            "id": req["id"],
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "serverInfo": {"name": "fake-server", "version": "1"},
            },
        }
        sys.stdout.write(json.dumps(resp) + "\\n")
        sys.stdout.flush()
        """,
    )
    info = probe_stdio(
        name="fake",
        command=sys.executable,
        args=[str(script)],
        timeout=5.0,
    )
    assert info.health == "ok"
    assert info.detail == "fake-server"
    assert info.latency_ms >= 0


def test_probe_stdio_spawn_error(tmp_path: Path) -> None:
    info = probe_stdio(
        name="nope",
        command=str(tmp_path / "nonexistent-binary-xyz"),
        timeout=2.0,
    )
    assert info.health == "spawn_error"


def test_probe_stdio_timeout(tmp_path: Path) -> None:
    script = _write_stdio_server(
        tmp_path,
        """
        import time
        time.sleep(10)
        """,
    )
    info = probe_stdio(
        name="hanging",
        command=sys.executable,
        args=[str(script)],
        timeout=0.5,
    )
    assert info.health == "timeout"


def test_probe_stdio_bad_response(tmp_path: Path) -> None:
    script = _write_stdio_server(
        tmp_path,
        """
        import sys
        sys.stdin.readline()
        sys.stdout.write("not-json-at-all\\n")
        sys.stdout.flush()
        """,
    )
    info = probe_stdio(
        name="bad",
        command=sys.executable,
        args=[str(script)],
        timeout=5.0,
    )
    assert info.health == "bad_response"


def test_probe_stdio_missing_env(tmp_path: Path) -> None:
    info = probe_stdio(
        name="x",
        command=sys.executable,
        env_overrides={"API_KEY": "${UNSET_VAR_XYZ_123}"},
        timeout=2.0,
    )
    assert info.health == "spawn_error"
    assert info.missing_env == ["UNSET_VAR_XYZ_123"]


def test_probe_stdio_jsonrpc_error(tmp_path: Path) -> None:
    script = _write_stdio_server(
        tmp_path,
        """
        import json, sys
        line = sys.stdin.readline()
        req = json.loads(line)
        resp = {
            "jsonrpc": "2.0",
            "id": req["id"],
            "error": {"code": -32600, "message": "Invalid request"},
        }
        sys.stdout.write(json.dumps(resp) + "\\n")
        sys.stdout.flush()
        """,
    )
    info = probe_stdio(
        name="jerror",
        command=sys.executable,
        args=[str(script)],
        timeout=5.0,
    )
    assert info.health == "bad_response"
    assert "Invalid request" in info.detail


# -- HTTP tests ---------------------------------------------------------------


class _FakeHandler(http.server.BaseHTTPRequestHandler):
    """Configurable handler driven by class attrs."""

    response_status: int = 200
    response_body: bytes = b'{"jsonrpc":"2.0","id":1,"result":{"serverInfo":{"name":"fake-http"}}}'
    www_auth: str = ""

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        self.send_response(self.response_status)
        if self.www_auth:
            self.send_header("WWW-Authenticate", self.www_auth)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(self.response_body)

    def log_message(self, *args: object) -> None:  # silence server logs
        pass


@pytest.fixture
def http_server() -> Iterator[tuple[str, type[_FakeHandler]]]:
    """Start a local HTTP server on an ephemeral port. Returns (url, handler_class)."""
    handler_cls = type("Handler", (_FakeHandler,), {})
    with socketserver.TCPServer(("127.0.0.1", 0), handler_cls) as srv:
        thread = threading.Thread(target=srv.serve_forever, daemon=True)
        thread.start()
        port = srv.server_address[1]
        yield f"http://127.0.0.1:{port}/", handler_cls
        srv.shutdown()


def test_probe_http_ok(http_server: tuple[str, type[_FakeHandler]]) -> None:
    url, _ = http_server
    info = probe_http(name="h", url=url, timeout=5.0)
    assert info.health == "ok"
    assert info.detail == "fake-http"


def test_probe_http_needs_oauth(http_server: tuple[str, type[_FakeHandler]]) -> None:
    url, handler_cls = http_server
    handler_cls.response_status = 401
    handler_cls.www_auth = 'Bearer realm="example"'
    handler_cls.response_body = b"unauthorized"
    info = probe_http(name="h", url=url, timeout=5.0)
    assert info.health == "needs_oauth"


def test_probe_http_error(http_server: tuple[str, type[_FakeHandler]]) -> None:
    url, handler_cls = http_server
    handler_cls.response_status = 500
    handler_cls.www_auth = ""
    handler_cls.response_body = b"server error"
    info = probe_http(name="h", url=url, timeout=5.0)
    assert info.health == "http_error"


def test_probe_http_unreachable() -> None:
    # Unroutable address: link-local 169.254 should fail fast
    info = probe_http(name="h", url="http://127.0.0.1:1/", timeout=1.0)
    assert info.health in ("unreachable", "timeout")


# -- router tests -------------------------------------------------------------


def test_probe_server_entry_http(http_server: tuple[str, type[_FakeHandler]]) -> None:
    url, _ = http_server
    entry = {"type": "http", "url": url}
    info = probe_server_entry("x", entry, timeout=5.0)
    assert info.health == "ok"


def test_probe_all_serial(tmp_path: Path) -> None:
    script = _write_stdio_server(
        tmp_path,
        """
        import json, sys
        line = sys.stdin.readline()
        req = json.loads(line)
        resp = {"jsonrpc":"2.0","id":req["id"],"result":{"serverInfo":{"name":"x"}}}
        sys.stdout.write(json.dumps(resp)+"\\n")
        sys.stdout.flush()
        """,
    )
    servers = {
        "a": {"type": "local", "command": sys.executable, "args": [str(script)]},
        "b": {"type": "local", "command": sys.executable, "args": [str(script)]},
    }
    results = probe_all(servers, timeout=5.0)
    assert len(results) == 2
    assert all(r.health == "ok" for r in results)


def test_default_timeout_is_two_seconds() -> None:
    # Sanity check: the policy (serial, 2s) is baked in.
    assert DEFAULT_TIMEOUT == 2.0


def test_health_info_default() -> None:
    h = HealthInfo(name="x", server_type="local", health="ok")
    assert h.missing_env == []
    assert h.detail == ""
