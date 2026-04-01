"""Optional dependency installs — LSP servers, MarkItDown, QMD, Playwright."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from copilotsetup.models import UIProtocol

# On Windows, npm/npx/node/rustup are .cmd shims that require shell=True.
_SHELL = sys.platform == "win32"

logger = logging.getLogger(__name__)


def _npm_needs_admin() -> bool:
    """Check if npm global installs require elevated privileges."""
    npm = shutil.which("npm")
    if not npm:
        return False
    try:
        r = subprocess.run(["npm", "config", "get", "prefix"], capture_output=True, text=True, shell=_SHELL)
        prefix = r.stdout.strip()
        if prefix and Path(prefix).exists():
            test = Path(prefix) / ".copilot-write-test"
            try:
                test.write_text("")
                test.unlink()
                return False
            except OSError:
                return True
    except Exception:
        logger.debug("Could not check npm admin requirement", exc_info=True)
    return False


def _npm_install_global(packages: list[str], ui: UIProtocol) -> bool:
    """Install npm packages globally, handling admin requirements."""
    needs_admin = _npm_needs_admin()
    if needs_admin and os.name == "nt":
        import ctypes

        is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
        if not is_admin:
            ui.print_msg("Node is installed system-wide — global npm installs need Administrator", "warn")
            ui.print_msg("Re-run as Administrator, or use nvm-windows for user-scoped Node.", "info")
            return False
    r = subprocess.run(["npm", "install", "-g", *packages], capture_output=True, text=True, shell=_SHELL)
    return r.returncode == 0


def _validate_lsp(command: str, args: list[str]) -> bool:
    from copilotsetup.platform_ops import validate_lsp_binary

    return validate_lsp_binary(command, args)


# ---------------------------------------------------------------------------
# Data-driven LSP tool definitions
# ---------------------------------------------------------------------------

_LSP_TOOLS = [
    {
        "name": "typescript-language-server",
        "check_cmd": "typescript-language-server",
        "check_args": ["--stdio"],
        "description": [
            "TypeScript Language Server gives the agent code intelligence for",
            ".ts, .tsx, .js, and .jsx files (types, definitions, references).",
        ],
        "install": lambda ui: _npm_install_global(["typescript-language-server", "typescript"], ui),
    },
    {
        "name": "pyright-langserver",
        "check_cmd": "pyright-langserver",
        "check_args": ["--stdio"],
        "description": [
            "Pyright gives the agent code intelligence for Python files",
            "(type checking, definitions, references).",
        ],
        "install": lambda ui: _npm_install_global(["pyright"], ui),
    },
]


# ---------------------------------------------------------------------------
# Confirm / install / summary helper for special-case tools
# ---------------------------------------------------------------------------


def _offer_install(
    ui: UIProtocol,
    name: str,
    description: list[str],
    install_fn: Callable[[], bool],
    summary: dict,
    *,
    default: bool = True,
) -> bool:
    """Show description, confirm, install, update summary. Returns True if installed."""
    print()
    for line in description:
        print(f"  {line}")
    print()
    if ui.confirm(f"Install {name}?", default=default):
        ui.print_msg(f"Installing {name}…", "info")
        if install_fn():
            ui.print_msg(f"{name} installed", "success")
            summary["optional_installed"].append(name)
            return True
        ui.print_msg(f"{name} install failed", "err")
        summary["optional_failed"].append(name)
        return False
    ui.print_msg(f"Skipped {name}", "info")
    summary["optional_skipped"].append(name)
    return False


def run_optional_deps(ui: UIProtocol, lsp_json_path: Path, lsp_config_path: Path, summary: dict) -> None:
    """Interactive optional dependency installs."""
    ui.section("Optional Dependencies")
    ui.print_msg("These tools enhance specific skills. Install now or later.", "info")
    ui.print_msg("The agent works without them but some skills will be limited.", "info")

    lsp_installed_any = False

    # ── Data-driven LSP tools ─────────────────────────────────────────────
    for tool in _LSP_TOOLS:
        name = tool["name"]
        if _validate_lsp(tool["check_cmd"], tool["check_args"]):
            ui.print_msg(f"{name} already installed", "success")
            summary["optional_skipped"].append(name)
            continue
        if shutil.which(tool["check_cmd"]):
            ui.print_msg(f"{name} found on PATH but not working", "warn")
        print()
        for line in tool["description"]:
            print(f"  {line}")
        print()
        if ui.confirm(f"Install {name}?", default=True):
            ui.print_msg(f"Installing {name}…", "info")
            if tool["install"](ui):
                ui.print_msg(f"{name} installed", "success")
                summary["optional_installed"].append(name)
                lsp_installed_any = True
            else:
                ui.print_msg(f"{name} install failed", "err")
                summary["optional_failed"].append(name)
        else:
            ui.print_msg(f"Skipped {name}", "info")
            summary["optional_skipped"].append(name)

    # ── Rust Analyzer (special: requires rustup) ─────────────────────────
    if _validate_lsp("rust-analyzer", []):
        ui.print_msg("rust-analyzer already installed", "success")
        summary["optional_skipped"].append("rust-analyzer")
    else:
        if shutil.which("rust-analyzer"):
            ui.print_msg("rust-analyzer found on PATH but not working", "warn")
        if not shutil.which("rustup"):
            print()
            print("  rust-analyzer requires the Rust toolchain, which isn't installed.")
            print("  To install Rust: https://rustup.rs")
            print("  After installing Rust, re-run setup to add rust-analyzer.")
            print()
            summary["optional_skipped"].append("rust-analyzer")
        else:

            def _install_rust_analyzer():
                r = subprocess.run(
                    ["rustup", "component", "add", "rust-analyzer"],
                    capture_output=True,
                    text=True,
                    shell=_SHELL,
                )
                return r.returncode == 0

            if _offer_install(
                ui,
                "rust-analyzer",
                ["rust-analyzer gives the agent code intelligence for Rust files."],
                _install_rust_analyzer,
                summary,
            ):
                lsp_installed_any = True

    # ── MarkItDown (special: pipx/pip fallback) ──────────────────────────
    if shutil.which("markitdown"):
        ui.print_msg("MarkItDown already installed", "success")
        summary["optional_skipped"].append("markitdown")
    else:
        _offer_install(
            ui,
            "MarkItDown",
            [
                "MarkItDown lets the agent read PDF, Word, Excel, and PowerPoint",
                "files by converting them to markdown text.",
            ],
            lambda: _install_markitdown(ui),
            summary,
        )

    # ── QMD (special: Node 22+ prerequisite) ─────────────────────────────
    if shutil.which("qmd"):
        ui.print_msg("QMD already installed", "success")
        summary["optional_skipped"].append("qmd")
    else:
        node_ok = False
        node_path = shutil.which("node")
        if node_path:
            try:
                r = subprocess.run(["node", "--version"], capture_output=True, text=True, shell=_SHELL)
                ver = r.stdout.strip().lstrip("v")
                major = int(ver.split(".")[0])
                if major >= 22:
                    node_ok = True
            except Exception:
                logger.debug("Could not determine Node.js version", exc_info=True)
        if not node_ok:
            node_ver_str = "not found"
            if node_path:
                try:
                    node_ver_str = subprocess.run(
                        ["node", "--version"], capture_output=True, text=True, shell=_SHELL
                    ).stdout.strip()
                except Exception:
                    logger.debug("Could not read Node.js version string", exc_info=True)
            ui.print_msg(f"QMD requires Node.js 22+ (current: {node_ver_str})", "warn")
            summary["optional_skipped"].append("qmd")
        else:
            _offer_install(
                ui,
                "QMD",
                [
                    "QMD (Query MarkDown) provides local hybrid search for the",
                    "agent's memory. Requires Node.js 22+.",
                ],
                lambda: _npm_install_global(["@tobilu/qmd"], ui),
                summary,
            )

    # ── Playwright Edge driver (special: directory check) ────────────────
    edge_installed = False
    if os.name == "nt":
        ms_pw_dir = Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright"
    else:
        ms_pw_dir = Path.home() / ".cache" / "ms-playwright"
    if ms_pw_dir.exists():
        edge_dirs = [d for d in ms_pw_dir.iterdir() if d.is_dir() and "msedge" in d.name]
        if edge_dirs:
            edge_installed = True

    if edge_installed:
        ui.print_msg("Playwright Edge driver already installed", "success")
        summary["optional_skipped"].append("playwright-edge")
    else:

        def _install_playwright_edge():
            r = subprocess.run(
                ["npx", "playwright", "install", "msedge"],
                capture_output=True,
                text=True,
                shell=_SHELL,
                encoding="utf-8",
                errors="replace",
            )
            return r.returncode == 0

        _offer_install(
            ui,
            "Playwright Edge driver",
            [
                "Playwright lets the agent interact with web browsers — take",
                "screenshots, click buttons, fill forms, and verify web apps.",
            ],
            _install_playwright_edge,
            summary,
            default=False,
        )

    # ── Re-generate LSP config if any LSP servers installed ──────────────
    lsp_items = {"typescript-language-server", "pyright-langserver", "rust-analyzer"}
    if lsp_installed_any and any(i in lsp_items for i in summary["optional_installed"]):
        from copilotsetup.config import generate_lsp_config

        count, skipped = generate_lsp_config(lsp_json_path, lsp_config_path, ui)
        summary["lsp_count"] = count
        summary["lsp_skipped"] = skipped


def _install_markitdown(ui: UIProtocol) -> bool:
    """Install MarkItDown via pipx (preferred) or pip fallback. Returns True on success."""
    pipx_cmd: str | None = None

    if shutil.which("pipx"):
        pipx_cmd = "pipx"
    elif shutil.which("pip"):
        print()
        ui.print_msg("pipx installs Python apps in isolated environments.", "info")
        ans = ui.confirm("Install pipx? (pip install --user pipx)", default=True)
        if ans:
            ui.print_msg("Installing pipx…", "info")
            r = subprocess.run(["pip", "install", "--user", "pipx"], capture_output=True, text=True, shell=_SHELL)
            if r.returncode == 0:
                ui.print_msg("pipx installed", "success")
                pipx_cmd = "python -m pipx"
            else:
                ui.print_msg("pipx install failed", "err")

    if pipx_cmd:
        ui.print_msg("Installing markitdown[all] via pipx…", "info")
        if pipx_cmd == "pipx":
            cmd = ["pipx", "install", "markitdown[all]"]
        else:
            cmd = ["python", "-m", "pipx", "install", "markitdown[all]"]
        r = subprocess.run(cmd, capture_output=True, text=True, shell=_SHELL)
        if r.returncode == 0:
            if not shutil.which("markitdown"):
                ui.print_msg("MarkItDown installed but not on PATH yet", "warn")
                ui.print_msg("Run: python -m pipx ensurepath  (then restart shell)", "info")
            else:
                ui.print_msg("MarkItDown installed", "success")
            return True
        ui.print_msg("MarkItDown install failed", "err")
        return False
    if shutil.which("pip"):
        ui.print_msg("Installing markitdown[all] via pip…", "info")
        r = subprocess.run(["pip", "install", "markitdown[all]"], capture_output=True, text=True, shell=_SHELL)
        if r.returncode == 0:
            ui.print_msg("MarkItDown installed", "success")
            return True
        ui.print_msg("MarkItDown install failed", "err")
        return False
    ui.print_msg("Neither pipx nor pip found — cannot install MarkItDown", "err")
    return False
