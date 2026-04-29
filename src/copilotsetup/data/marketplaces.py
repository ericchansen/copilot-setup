"""Marketplaces data provider — parses copilot plugin marketplace list output."""

from __future__ import annotations

import re
from dataclasses import dataclass

from copilotsetup.utils.cli import run_copilot

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
_MARKETPLACE_RE = re.compile(r"\s*([◆•])\s+(\S+)\s+\((.+?)\)")
_FALLBACK_RE = re.compile(r"\s*[◆•]\s+(\S+)")
_SOURCE_RE = re.compile(r"\((.+?)\)")


@dataclass(frozen=True)
class MarketplaceInfo:
    """A single Copilot CLI plugin marketplace registration."""

    name: str
    source: str = ""
    marketplace_type: str = "registered"


def _parse_marketplace_line(line: str) -> MarketplaceInfo | None:
    match = _MARKETPLACE_RE.match(line)
    if match:
        glyph, name, source = match.groups()
        marketplace_type = "builtin" if glyph == "◆" else "registered"
        return MarketplaceInfo(name=name, source=source, marketplace_type=marketplace_type)

    stripped = line.strip()
    if not stripped or stripped[0] not in {"◆", "•"}:
        return None

    name_match = _FALLBACK_RE.match(line)
    if not name_match:
        return None

    source_match = _SOURCE_RE.search(stripped)
    source = source_match.group(1) if source_match else ""
    return MarketplaceInfo(
        name=name_match.group(1),
        source=source,
        marketplace_type="unknown",
    )


class MarketplaceProvider:
    """Read-only provider that loads registered plugin marketplaces via CLI."""

    def load(self) -> list[MarketplaceInfo]:
        try:
            result = run_copilot("plugin", "marketplace", "list", timeout=30)
        except FileNotFoundError:
            return []
        except Exception:
            return []

        if result.returncode != 0:
            return []

        output = _ANSI_RE.sub("", result.stdout or "")
        if not output.strip():
            return []

        items: list[MarketplaceInfo] = []
        for line in output.splitlines():
            item = _parse_marketplace_line(line)
            if item is not None:
                items.append(item)
        return items
