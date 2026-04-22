"""LSP Servers data provider — reads lsp-config.json."""

from __future__ import annotations

from dataclasses import dataclass

from copilotsetup.config import lsp_config_json
from copilotsetup.platform_ops import validate_lsp_binary
from copilotsetup.utils.file_io import read_json


@dataclass(frozen=True)
class LspInfo:
    """A single LSP server entry from lsp-config.json."""

    name: str
    command: str
    args: tuple[str, ...] = ()
    binary_ok: bool = False

    @property
    def status(self) -> str:
        return "enabled" if self.binary_ok else "missing"

    @property
    def reason(self) -> str:
        return "" if self.binary_ok else "binary not found"


class LspServerProvider:
    """Read-only provider that loads LSP server definitions."""

    def load(self) -> list[LspInfo]:
        data = read_json(lsp_config_json())
        if not isinstance(data, dict):
            return []
        servers = data.get("lspServers")
        if not isinstance(servers, dict):
            return []
        result: list[LspInfo] = []
        for name, entry in sorted(servers.items()):
            if not isinstance(entry, dict):
                continue
            command = str(entry.get("command", ""))
            args = entry.get("args") or []
            if not isinstance(args, list):
                args = []
            binary_ok = validate_lsp_binary(command, args) if command else False
            result.append(
                LspInfo(
                    name=str(name),
                    command=command,
                    args=tuple(str(a) for a in args),
                    binary_ok=binary_ok,
                )
            )
        return result
