# SPDX-License-Identifier: MIT
"""Project paths and dotted-path accessors."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from .errors import VaultError

RESUME_DIR = ".resume"
VAULT_FILE = "vault.yaml"
SESSION_FILE = "intake-session.json"
CONFIG_FILE = "config.yaml"


def find_project_root(start: Path | None = None) -> Path | None:
    """Return the nearest ancestor containing a .resume directory."""
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / RESUME_DIR).is_dir():
            return candidate
    return None


def require_project_root(start: Path | None = None) -> Path:
    root = find_project_root(start)
    if root is None:
        raise VaultError(
            "project.not_found",
            "No .resume directory found in this directory or any parent.",
            fix="Run `resume init` in the project root first.",
        )
    return root


def resume_dir(root: Path) -> Path:
    return root / RESUME_DIR


def vault_path(root: Path) -> Path:
    return resume_dir(root) / VAULT_FILE


def session_path(root: Path) -> Path:
    return resume_dir(root) / SESSION_FILE


def templates_dir() -> Path:
    override = os.environ.get("RESUME_PRO_TEMPLATES_DIR")
    if override:
        path = Path(override).expanduser().resolve()
        if path.is_dir():
            return path
        raise VaultError(
            "templates.dir_missing",
            f"RESUME_PRO_TEMPLATES_DIR points to a missing directory: {path}",
            fix="Unset the variable or point it at the repository's templates directory.",
        )
    here = Path(__file__).resolve()
    candidates = [
        here.parent / "templates",
        here.parents[2] / "templates",
        here.parents[1] / "templates",
    ]
    for candidate in candidates:
        if (candidate / "cn").is_dir() or (candidate / "en").is_dir():
            return candidate
    raise VaultError(
        "templates.dir_missing",
        "Could not locate the template library.",
        fix="Set RESUME_PRO_TEMPLATES_DIR or run from the repository root.",
    )


def schema_dir() -> Path:
    """Locate the schema directory in source checkouts and installed packages."""
    override = os.environ.get("RESUME_PRO_SCHEMA_DIR")
    if override:
        path = Path(override).expanduser().resolve()
        if path.is_dir():
            return path
        raise VaultError(
            "schema.dir_missing",
            f"RESUME_PRO_SCHEMA_DIR points to a missing directory: {path}",
            fix="Unset the variable or point it at the repository's schema directory.",
        )

    here = Path(__file__).resolve()
    candidates = [
        here.parent / "schema",          # packaged alongside the module
        here.parents[2] / "schema",      # src/resume_pro -> repository root
        here.parents[1] / "schema",
    ]
    for candidate in candidates:
        if (candidate / "vault.schema.json").is_file():
            return candidate
    raise VaultError(
        "schema.dir_missing",
        "Could not locate vault.schema.json.",
        fix="Set RESUME_PRO_SCHEMA_DIR to the schema directory, or run from the repository root.",
    )


_TOKEN_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)(?:\[(\d+)\])?$")


def parse_path(path: str) -> list[tuple[str, int | None]]:
    if not path:
        raise ValueError("empty path")
    segments: list[tuple[str, int | None]] = []
    for raw in path.split("."):
        match = _TOKEN_RE.match(raw)
        if not match:
            raise ValueError(f"invalid path segment: {raw!r}")
        segments.append((match.group(1), int(match.group(2)) if match.group(2) is not None else None))
    return segments


def get_path(data: Any, path: str, default: Any = None) -> Any:
    current = data
    for key, index in parse_path(path):
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
        if index is not None:
            if not isinstance(current, list) or index >= len(current):
                return default
            current = current[index]
    return current


def set_path(data: dict[str, Any], path: str, value: Any) -> None:
    segments = parse_path(path)
    current: Any = data
    for position, (key, index) in enumerate(segments):
        last = position == len(segments) - 1
        if last:
            if index is None:
                if not isinstance(current, dict):
                    raise ValueError(f"cannot set {path!r}: parent is not an object")
                current[key] = value
            else:
                if not isinstance(current, dict):
                    raise ValueError(f"cannot set {path!r}: parent is not an object")
                items = current.setdefault(key, [])
                if not isinstance(items, list):
                    raise ValueError(f"cannot set {path!r}: {key!r} is not a list")
                while len(items) <= index:
                    items.append({})
                items[index] = value
            return

        if index is None:
            if not isinstance(current, dict):
                raise ValueError(f"cannot traverse {path!r}: parent is not an object")
            current = current.setdefault(key, {})
        else:
            if not isinstance(current, dict):
                raise ValueError(f"cannot traverse {path!r}: parent is not an object")
            items = current.setdefault(key, [])
            if not isinstance(items, list):
                raise ValueError(f"cannot traverse {path!r}: {key!r} is not a list")
            while len(items) <= index:
                items.append({})
            current = items[index]


def delete_path(data: dict[str, Any], path: str) -> None:
    segments = parse_path(path)
    current: Any = data
    for position, (key, index) in enumerate(segments):
        last = position == len(segments) - 1
        if index is None:
            if not isinstance(current, dict) or key not in current:
                return
            if last:
                del current[key]
                return
            current = current[key]
        else:
            if not isinstance(current, dict) or key not in current:
                return
            items = current[key]
            if not isinstance(items, list) or index >= len(items):
                return
            if last:
                del items[index]
                return
            current = items[index]
