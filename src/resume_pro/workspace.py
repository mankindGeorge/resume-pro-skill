# SPDX-License-Identifier: MIT
"""Publish user-facing artifacts into the per-project workspace."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

WORKSPACE_DIR = "workspace"


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-._")
    return slug[:80] or "project"


def workspace_dir(root: Path, slug: str) -> Path:
    directory = Path(root) / WORKSPACE_DIR / _safe_slug(slug)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def publish_workspace(root: Path, slug: str, files: list[Path]) -> Path:
    """Copy user-facing files into workspace/<slug>/ and return the folder."""
    target = workspace_dir(root, slug)
    for source in files:
        path = Path(source)
        if path.is_file():
            shutil.copy2(path, target / path.name)
    return target
