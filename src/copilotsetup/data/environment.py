"""Environment data provider — reads Copilot-relevant environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass

from copilotsetup.config import ENV_PREFIXES, SENSITIVE_PATTERNS


@dataclass(frozen=True)
class EnvVarInfo:
    """A single environment variable relevant to Copilot CLI."""

    name: str
    value: str
    is_sensitive: bool = False


def _is_sensitive(name: str) -> bool:
    upper = name.upper()
    return any(p in upper for p in SENSITIVE_PATTERNS)


def _mask(value: str) -> str:
    if len(value) <= 4:
        return "****"
    return value[:2] + "…" + value[-2:]


class EnvironmentProvider:
    """Read-only provider that scans ``os.environ`` for relevant variables."""

    def load(self) -> list[EnvVarInfo]:
        items: list[EnvVarInfo] = []
        for key, val in sorted(os.environ.items()):
            if any(key.upper().startswith(p) for p in ENV_PREFIXES):
                sensitive = _is_sensitive(key)
                items.append(
                    EnvVarInfo(
                        name=key,
                        value=_mask(val) if sensitive else val,
                        is_sensitive=sensitive,
                    )
                )
        return items
