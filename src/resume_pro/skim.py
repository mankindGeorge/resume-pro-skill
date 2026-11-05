# SPDX-License-Identifier: MIT
"""The 10-second campus skim test."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from . import profile

AI_TERMS = re.compile(
    r"\b(ai|llm|rag|aigc|agent|prompt|transformer|deep learning|machine learning|nlp|cv)\b|大模型|人工智能|机器学习|深度学习|检索增强",
    re.IGNORECASE,
)


@dataclass
class SkimResult:
    passed: bool
    found: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "found": self.found,
            "missing": self.missing,
            "notes": self.notes,
        }


def skim_test(vault: dict, market: str, persona: str) -> SkimResult:
    identity = vault.get("identity") or {}
    skills = vault.get("skills") or []
    experience = vault.get("experience") or []
    projects = vault.get("projects") or []
    found: list[str] = []
    missing: list[str] = []
    notes: list[str] = []

    if identity.get("full_name") and (identity.get("email") or identity.get("phone")):
        found.append("name/contact")
    else:
        missing.append("name/contact")

    if vault.get("education"):
        found.append("education")
    else:
        missing.append("education")

    skill_names = [item.get("name", "") for group in skills for item in group.get("items") or []]
    signals = 0
    if len(skill_names) >= 3:
        found.append("core_skills")
        signals += 1
    else:
        missing.append("core_skills")

    ai_text = " ".join(
        [str(item.get("name", "")) for group in skills for item in group.get("items") or []]
        + [" ".join(str(v) for v in (bullet.get("text") or {}).values()) for role in experience for bullet in role.get("bullets") or []]
        + [" ".join(str(v) for v in (bullet.get("text") or {}).values()) for project in projects for bullet in project.get("bullets") or []]
    )
    if any(group.get("kind") == "ai_ml" for group in skills) or AI_TERMS.search(ai_text):
        found.append("ai_related")
        signals += 1
    else:
        missing.append("ai_related")

    if any(role.get("employment_type") == "internship" for role in experience):
        found.append("internship")
        signals += 1
    else:
        missing.append("internship")

    if projects:
        found.append("projects")
        signals += 1
    else:
        missing.append("projects")

    if profile.is_student(persona):
        if signals < 2:
            notes.append("A 10-second skim finds fewer than two of the four core signals.")
        if not vault.get("education"):
            notes.append("Education must be visible in the first screen.")
    passed = bool(identity.get("full_name")) and bool(vault.get("education")) and signals >= 2
    return SkimResult(passed=passed, found=found, missing=missing, notes=notes)
