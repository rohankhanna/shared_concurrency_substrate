"""Version helpers for Gate."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from importlib import resources


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


def _resource_version() -> str | None:
    try:
        data = resources.files("gate").joinpath("VERSION").read_text().strip()
    except Exception:
        return None
    return data or None


def _repo_version(repo_root: Path) -> str | None:
    version_path = repo_root / "src" / "gate" / "VERSION"
    if version_path.exists():
        data = version_path.read_text().strip()
        return data or None
    return None


def get_version() -> str:
    env_version = os.environ.get("GATE_VERSION")
    if env_version:
        return env_version
    resource_version = _resource_version()
    if resource_version:
        return resource_version
    repo_root = _find_repo_root()
    if repo_root:
        repo_version = _repo_version(repo_root)
        if repo_version:
            return repo_version
        sha = _git_version(repo_root)
        if sha:
            return f"dev-{sha}"
    return "unknown"
