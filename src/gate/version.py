"""Version helpers for Gate."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def _find_repo_root() -> Path | None:
    here = Path(__file__).resolve()
    for parent in [here] + list(here.parents):
        if (parent / "systems" / "gate_vm" / "systemd" / "gate-broker.service").exists():
            return parent
    return None


def _git_version(repo_root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
    except Exception:
        return None
    sha = result.stdout.strip()
    return sha or None


def get_version() -> str:
    env_version = os.environ.get("GATE_VERSION")
    if env_version:
        return env_version
    repo_root = _find_repo_root()
    if repo_root:
        sha = _git_version(repo_root)
        if sha:
            return f"dev-{sha}"
    return "unknown"
