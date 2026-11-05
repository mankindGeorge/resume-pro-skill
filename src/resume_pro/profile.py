# SPDX-License-Identifier: MIT
"""Load market and persona profiles."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from .errors import VaultError

MARKET_IDS = ("intl_en", "cn_internet", "cn_soe", "cn_finance", "cn_creative", "hk_sg", "academic")
PERSONA_IDS = (
    "student_no_projects",
    "student_with_projects",
    "student_with_internship",
    "new_grad",
    "career_switcher",
    "experienced",
    "senior_manager",
    "academic",
    "creative",
)
STUDENT_PERSONAS = ("student_no_projects", "student_with_projects", "student_with_internship", "new_grad")


def profiles_dir() -> Path:
    override = os.environ.get("RESUME_PRO_PROFILES_DIR")
    if override:
        path = Path(override).expanduser().resolve()
        if path.is_dir():
            return path
        raise VaultError(
            "profiles.dir_missing",
            f"RESUME_PRO_PROFILES_DIR points to a missing directory: {path}",
            fix="Unset the variable or point it at the repository's profiles directory.",
        )
    here = Path(__file__).resolve()
    candidates = [
        here.parent / "profiles",
        here.parents[2] / "profiles",
        here.parents[1] / "profiles",
    ]
    for candidate in candidates:
        if (candidate / "markets").is_dir():
            return candidate
    raise VaultError(
        "profiles.dir_missing",
        "Could not locate the profiles directory.",
        fix="Set RESUME_PRO_PROFILES_DIR or run from the repository root.",
    )


@lru_cache(maxsize=None)
def load_market(market_id: str) -> dict[str, Any]:
    path = profiles_dir() / "markets" / f"{market_id}.yaml"
    return _load(path, "market", market_id)


@lru_cache(maxsize=None)
def load_persona(persona_id: str) -> dict[str, Any]:
    path = profiles_dir() / "personas" / f"{persona_id}.yaml"
    return _load(path, "persona", persona_id)


def _load(path: Path, kind: str, expected_id: str) -> dict[str, Any]:
    if not path.is_file():
        raise VaultError(
            f"profiles.{kind}_missing",
            f"No {kind} profile named {expected_id!r}.",
            path=str(path),
            fix=f"Use one of: {', '.join(MARKET_IDS if kind == 'market' else PERSONA_IDS)}.",
        )
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise VaultError(
            f"profiles.{kind}_invalid",
            f"Could not read {path}: {exc}",
            fix="Fix the YAML file or restore it from version control.",
        ) from exc
    if not isinstance(data, dict) or data.get("id") != expected_id:
        raise VaultError(
            f"profiles.{kind}_invalid",
            f"{path} must define id: {expected_id}.",
            fix="Make the file name and the id field identical.",
        )
    return data


def list_markets() -> list[dict[str, Any]]:
    return [load_market(m) for m in MARKET_IDS]


def list_personas() -> list[dict[str, Any]]:
    return [load_persona(p) for p in PERSONA_IDS]


def is_student(persona_id: str) -> bool:
    return persona_id in STUDENT_PERSONAS


def is_experimental(profile: dict[str, Any]) -> bool:
    return profile.get("status") == "experimental"
