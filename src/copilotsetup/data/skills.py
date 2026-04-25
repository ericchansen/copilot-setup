"""Skills data provider — scans ~/.copilot/skills/ and plugin-bundled skills."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from copilotsetup.config import config_json, installed_plugins_dir, skills_dir
from copilotsetup.platform_ops import get_link_target, is_link
from copilotsetup.utils.file_io import read_json


@dataclass(frozen=True)
class SkillInfo:
    """A single skill entry discovered under the skills directory."""

    name: str
    source: str = ""
    link_target: str = ""
    link_ok: bool = False
    is_linked: bool = False
    is_real_dir: bool = False
    plugin_bundled: bool = False

    @property
    def status(self) -> str:
        if self.plugin_bundled:
            return "enabled"
        if self.is_real_dir:
            return "enabled"
        if self.is_linked:
            return "enabled" if self.link_ok else "broken"
        return "missing"

    @property
    def reason(self) -> str:
        if self.is_linked and not self.link_ok:
            return "dangling link"
        return ""


class SkillProvider:
    """Read-only provider that scans the skills directory and plugin bundles."""

    def load(self) -> list[SkillInfo]:
        result: list[SkillInfo] = []
        seen: set[str] = set()

        # 1. Skills from ~/.copilot/skills/ directory
        sd = skills_dir()
        if sd.is_dir():
            for entry in sorted(sd.iterdir()):
                linked = is_link(entry)
                target_str = ""
                link_ok = False
                real_dir = False
                if linked:
                    target = get_link_target(entry)
                    if target:
                        target_str = str(target)
                        link_ok = target.exists()
                else:
                    real_dir = entry.is_dir()
                source = ""
                if target_str:
                    source = Path(target_str).parent.name
                elif real_dir:
                    source = "local"
                seen.add(entry.name)
                result.append(
                    SkillInfo(
                        name=entry.name,
                        source=source,
                        link_target=target_str,
                        link_ok=link_ok,
                        is_linked=linked,
                        is_real_dir=real_dir,
                    )
                )

        # 2. Plugin-bundled skills not already in the list
        for plugin_name, plugin_path in self._find_plugin_skill_dirs():
            skills_subdir = plugin_path / "skills"
            if not skills_subdir.is_dir():
                continue
            for folder in sorted(skills_subdir.iterdir()):
                if folder.is_dir() and folder.name not in seen:
                    seen.add(folder.name)
                    result.append(
                        SkillInfo(
                            name=folder.name,
                            source=plugin_name,
                            plugin_bundled=True,
                        )
                    )

        return result

    @staticmethod
    def _find_plugin_skill_dirs() -> list[tuple[str, Path]]:
        """Return (plugin_name, install_path) for installed plugins."""
        cfg = read_json(config_json())
        if not isinstance(cfg, dict):
            return []
        plugins_dir = installed_plugins_dir()
        pairs: list[tuple[str, Path]] = []
        for entry in cfg.get("installedPlugins", []) or []:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name")
            cache_path = entry.get("cache_path", "")
            if not name or not cache_path:
                continue
            candidate = plugins_dir / cache_path
            if candidate.is_dir():
                pairs.append((str(name), candidate))
        return pairs
