"""Git authentication detection."""

from __future__ import annotations

import re
import subprocess

from copilotsetup.models import UIProtocol


def detect_git_auth(ui: UIProtocol, auth_state: dict) -> None:
    """Detect available git authentication methods and populate *auth_state*."""

    # -- GitHub CLI ---------------------------------------------------------
    try:
        r = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
        )
        combined = r.stdout + r.stderr
        accounts = re.findall(r"Logged in to github\.com account (\S+)", combined)
        if accounts:
            auth_state["gh_available"] = True
            ui.print_msg(f"GitHub CLI: logged in as {', '.join(accounts)}", "success")
            if len(accounts) > 1:
                # Find which account is active: "account NAME (...)\n  - Active account: true"
                active = re.search(
                    r"account (\S+)\s+\(keyring\)\s*\n\s*-\s*Active account:\s*true",
                    combined,
                )
                if active:
                    ui.print_msg(f"Active account: {active.group(1)}", "info")
        else:
            ui.print_msg("GitHub CLI (gh) installed but not logged in", "warn")
    except FileNotFoundError:
        ui.print_msg("GitHub CLI (gh) not installed", "warn")

    # -- SSH ----------------------------------------------------------------
    try:
        r = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", "-T", "git@github.com"],
            capture_output=True,
            text=True,
        )
        combined = r.stdout + r.stderr
        m = re.search(r"Hi (\S+)!", combined)
        if m:
            auth_state["ssh_available"] = True
            auth_state["prefer_ssh"] = True
            ui.print_msg(f"SSH: authenticated as {m.group(1)}", "success")
        else:
            ui.print_msg("SSH to github.com not available — using HTTPS", "info")
    except FileNotFoundError:
        ui.print_msg("SSH client not found — using HTTPS", "info")
