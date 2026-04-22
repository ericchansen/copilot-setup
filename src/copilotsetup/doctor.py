"""Health probes for MCP servers.

The ``doctor`` module probes live MCP servers (stdio and HTTP) and reports
their status.  Used by ``copilot-setup doctor`` CLI subcommand.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Literal

from copilotsetup.config import mcp_config_json
from copilotsetup.utils.file_io import read_json

logger = logging.getLogger(__name__)

Health = Literal[
    "ok",
    "timeout",
    "spawn_error",
    "bad_response",
    "needs_oauth",
    "http_error",
    "unreachable",
    "unknown",
]

DEFAULT_TIMEOUT = 2.0
MCP_PROTOCOL_VERSION = "2024-11-05"


@dataclass
class HealthInfo:
    """Result of probing a single MCP server."""

    name: str
    server_type: str  # "local" or "http"
    health: Health
    detail: str = ""
    latency_ms: int = 0
    missing_env: list[str] = field(default_factory=list)


# -- env helpers ---------------------------------------------------------------


def _build_env(
    env_overrides: dict[str, str] | None,
) -> tuple[dict[str, str], list[str]]:
    """Merge process env with overrides; return (env, missing)."""
    env = os.environ.copy()
    missing: list[str] = []
    if not env_overrides:
        return env, missing
    for k, raw in env_overrides.items():
        v = raw
        if isinstance(v, str):
            var_name: str | None = None
            if v.startswith("${") and v.endswith("}"):
                var_name = v[2:-1]
            elif v.startswith("$") and len(v) > 1 and v[1:].replace("_", "").isalnum():
                var_name = v[1:]
            if var_name is not None:
                resolved = os.environ.get(var_name)
                if resolved is None:
                    missing.append(var_name)
                    continue
                v = resolved
        env[k] = str(v)
    return env, missing


class _suppress_errors:
    """Context manager: suppress everything except KeyboardInterrupt."""

    def __enter__(self) -> None:
        return None

    def __exit__(self, exc_type, exc, tb) -> bool:
        return exc_type is not None and not issubclass(exc_type, KeyboardInterrupt)


# -- stdio probes --------------------------------------------------------------


def probe_stdio(
    name: str,
    command: str,
    args: list[str] | None = None,
    env_overrides: dict[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> HealthInfo:
    """Spawn an MCP stdio server, send ``initialize``, classify the response."""
    args = args or []
    env, missing = _build_env(env_overrides)
    info = HealthInfo(name=name, server_type="local", health="unknown", missing_env=list(missing))
    if missing:
        info.health = "spawn_error"
        info.detail = f"missing env: {', '.join(missing)}"
        return info

    init_payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "copilot-setup-doctor", "version": "0.1"},
        },
    }
    message = json.dumps(init_payload) + "\n"

    start = time.monotonic()
    try:
        proc = subprocess.Popen(
            [command, *args],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True,
        )
    except (OSError, FileNotFoundError) as exc:
        info.health = "spawn_error"
        info.detail = str(exc)
        return info

    try:
        stdout, stderr = proc.communicate(input=message, timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        with _suppress_errors():
            proc.wait(timeout=1.0)
        info.health = "timeout"
        info.detail = f"no response in {timeout}s"
        return info
    finally:
        info.latency_ms = int((time.monotonic() - start) * 1000)

    if not stdout.strip():
        info.health = "bad_response"
        err = (stderr or "").strip().splitlines()
        info.detail = err[-1] if err else "empty response"
        return info

    first_line = stdout.strip().splitlines()[0]
    try:
        resp = json.loads(first_line)
    except json.JSONDecodeError:
        info.health = "bad_response"
        info.detail = f"non-JSON: {first_line[:80]}"
        return info

    if "result" in resp:
        info.health = "ok"
        server_info = resp["result"].get("serverInfo", {})
        if server_info:
            info.detail = server_info.get("name", "")
        return info
    if "error" in resp:
        info.health = "bad_response"
        info.detail = str(resp["error"].get("message", resp["error"]))[:120]
        return info

    info.health = "bad_response"
    info.detail = "no result or error in response"
    return info


# -- HTTP probes ---------------------------------------------------------------


def probe_http(
    name: str,
    url: str,
    headers: dict[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> HealthInfo:
    """POST an MCP ``initialize`` to the URL and classify the response."""
    info = HealthInfo(name=name, server_type="http", health="unknown")
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "copilot-setup-doctor", "version": "0.1"},
        },
    }
    body = json.dumps(payload).encode("utf-8")
    req_headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if headers:
        req_headers.update(headers)

    req = urllib.request.Request(url, data=body, headers=req_headers, method="POST")
    start = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            info.latency_ms = int((time.monotonic() - start) * 1000)
            data = resp.read(4096)
            if resp.status == 200:
                info.health = "ok"
                with _suppress_errors():
                    parsed = json.loads(data.decode("utf-8", errors="replace"))
                    server_info = parsed.get("result", {}).get("serverInfo", {})
                    if server_info:
                        info.detail = server_info.get("name", "")
                return info
            info.health = "http_error"
            info.detail = f"HTTP {resp.status}"
            return info
    except urllib.error.HTTPError as exc:
        info.latency_ms = int((time.monotonic() - start) * 1000)
        auth_header = exc.headers.get("WWW-Authenticate", "") if exc.headers else ""
        if exc.code == 401 and "bearer" in auth_header.lower():
            info.health = "needs_oauth"
            info.detail = "401 Bearer — OAuth required"
            return info
        if exc.code == 401:
            info.health = "needs_oauth" if auth_header else "http_error"
            info.detail = f"HTTP 401 {auth_header}".strip()
            return info
        info.health = "http_error"
        info.detail = f"HTTP {exc.code}"
        return info
    except TimeoutError:
        info.health = "timeout"
        info.detail = f"no response in {timeout}s"
        return info
    except urllib.error.URLError as exc:
        info.health = "unreachable"
        info.detail = str(exc.reason)[:120]
        return info
    except OSError as exc:
        info.health = "unreachable"
        info.detail = str(exc)[:120]
        return info


# -- Iteration -----------------------------------------------------------------


def probe_server_entry(
    name: str,
    entry: dict,
    timeout: float = DEFAULT_TIMEOUT,
) -> HealthInfo:
    """Route one mcpServers entry to the appropriate probe."""
    server_type = entry.get("type", "local")
    if server_type == "http":
        return probe_http(
            name=name,
            url=entry.get("url", ""),
            headers=entry.get("headers") or {},
            timeout=timeout,
        )
    return probe_stdio(
        name=name,
        command=entry.get("command", ""),
        args=entry.get("args") or [],
        env_overrides=entry.get("env") or {},
        timeout=timeout,
    )


def probe_all(
    servers: dict[str, dict],
    timeout: float = DEFAULT_TIMEOUT,
) -> list[HealthInfo]:
    """Probe every server serially."""
    return [probe_server_entry(name, entry, timeout=timeout) for name, entry in servers.items()]


# -- CLI -----------------------------------------------------------------------

_HEALTH_MARKERS: dict[Health, str] = {
    "ok": "✓",
    "timeout": "⏱",
    "spawn_error": "✗",
    "bad_response": "✗",
    "needs_oauth": "🔑",
    "http_error": "✗",
    "unreachable": "✗",
    "unknown": "?",
}


def _fmt_row(info: HealthInfo) -> str:
    marker = _HEALTH_MARKERS.get(info.health, "?")
    detail = info.detail or ""
    latency = f"{info.latency_ms}ms" if info.latency_ms else ""
    return f"  {marker} {info.name:<28} {info.health:<14} {latency:<8} {detail}"


def run_cli() -> int:
    """Entry point for ``copilot-setup doctor``.

    Reads mcp-config.json, probes each server, prints a report.
    Returns 0 if all ok, 1 if any unhealthy.
    """
    data = read_json(mcp_config_json())
    servers: dict[str, dict] = {}
    if isinstance(data, dict):
        raw = data.get("mcpServers")
        if isinstance(raw, dict):
            servers = {k: v for k, v in raw.items() if isinstance(v, dict)}

    if not servers:
        print("No MCP servers configured.")
        return 0

    print(f"Probing {len(servers)} MCP server(s)…")
    print()
    print(f"  {'':2} {'NAME':<28} {'HEALTH':<14} {'LATENCY':<8} DETAIL")
    print(f"  {'─' * 2} {'─' * 28} {'─' * 14} {'─' * 8} {'─' * 40}")

    results = probe_all(servers)
    exit_code = 0
    for info in results:
        print(_fmt_row(info))
        if info.health not in ("ok", "needs_oauth"):
            exit_code = 1

    print()
    ok_count = sum(1 for r in results if r.health == "ok")
    oauth_count = sum(1 for r in results if r.health == "needs_oauth")
    fail_count = len(results) - ok_count - oauth_count
    print(f"  {ok_count} ok, {oauth_count} need OAuth, {fail_count} failed")

    return exit_code
