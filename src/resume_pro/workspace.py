# SPDX-License-Identifier: MIT
"""Publish user-facing artifacts into the skill-root workspace."""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

WORKSPACE_DIR = "workspace"


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-._")
    return slug[:80] or "project"


def workspace_root() -> Path:
    override = os.environ.get("RESUME_PRO_WORKSPACE_DIR")
    if override:
        return Path(override).expanduser().resolve()
    here = Path(__file__).resolve()
    for candidate in (here.parents[2], here.parents[1]):
        if (candidate / "SKILL.md").is_file():
            return candidate / WORKSPACE_DIR
    return here.parents[2] / WORKSPACE_DIR


def workspace_dir(root: Path, slug: str) -> Path:
    """Return the project folder, or create one under the skill-root workspace."""
    root = Path(root).resolve()
    base = workspace_root()
    directory = root if root.parent == base else base / _safe_slug(slug)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def publish_workspace(root: Path, slug: str, files: list[Path]) -> Path:
    """Copy user-facing files into the project folder and return it."""
    target = workspace_dir(root, slug)
    for source in files:
        path = Path(source)
        if path.is_file():
            shutil.copy2(path, target / path.name)
    return target
