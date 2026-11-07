# SPDX-License-Identifier: MIT
"""Deterministic layout budgets and page estimation."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from .errors import ResumeProError

LINES_PER_PAGE = 46
EN_CHARS_PER_LINE = 90
ZH_CHARS_PER_LINE = 45
SKILLS_PER_LINE = 6


class LayoutError(ResumeProError):
    pass


@dataclass
class LayoutReport:
    pages: int
    target_pages: int
    max_pages: int
    lines: float
    bottom_whitespace_pct: int
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pages": self.pages,
            "target_pages": self.target_pages,
            "max_pages": self.max_pages,
            "lines": round(self.lines, 1),
            "bottom_whitespace_pct": self.bottom_whitespace_pct,
            "warnings": self.warnings,
        }


def _summary_lines(model: dict[str, Any]) -> float:
    summary = model.get("summary") or ""
    if not summary:
        return 0.0
    per_line = ZH_CHARS_PER_LINE if model.get("locale") == "zh" else EN_CHARS_PER_LINE
    return max(1.0, math.ceil(len(summary) / per_line))


def estimate_bullet_lines(bullet_texts: list[str], locale: str) -> float:
    """Shared bullet-line estimate used by both layout and lint, so the two
    estimators agree. Accounts for text length via the locale's chars-per-line
    instead of a fixed per-bullet coefficient."""
    per_line = ZH_CHARS_PER_LINE if locale == "zh" else EN_CHARS_PER_LINE
    return sum(max(1.0, math.ceil(len(str(text)) / per_line)) for text in bullet_texts)


def _content_lines(model: dict[str, Any]) -> float:
    lines = 4.0  # header and contact block
    lines += _summary_lines(model)
    for entry in model.get("education") or []:
        lines += 2.0
    for section in ("experience", "projects"):
        for entry in model.get(section) or []:
            lines += 2.0 if section == "experience" else 1.5
            lines += estimate_bullet_lines(entry.get("bullets") or [], model.get("locale", "en"))
    skill_count = sum(len(group.get("items") or []) for group in model.get("skills") or [])
    if skill_count:
        lines += 1.0 + math.ceil(skill_count / SKILLS_PER_LINE) * 0.6
    for section in ("awards", "certificates", "languages", "publications", "open_source"):
        lines += len(model.get(section) or []) * 0.6
    # One heading per populated section.
    populated = sum(
        1
        for section in ("summary", "education", "experience", "projects", "skills", "awards", "certificates", "languages", "publications", "open_source")
        if model.get(section)
    )
    lines += populated * 1.5
    return lines


def check_layout(
    model: dict[str, Any],
    manifest: dict[str, Any],
    application: dict[str, Any],
) -> LayoutReport:
    budgets = manifest.get("budgets") or {}
    errors: list[str] = []

    summary = model.get("summary") or ""
    if summary:
        limit = (budgets.get("summary_chars") or {}).get(model.get("locale", "en"), 240)
        if len(summary) > int(limit):
            errors.append(f"Summary is {len(summary)} characters; the template allows {limit}.")
    if len(model.get("experience") or []) > int(budgets.get("max_roles", 5)):
        errors.append(f"{len(model['experience'])} roles exceed the template budget.")
    if len(model.get("projects") or []) > int(budgets.get("max_projects", 4)):
        errors.append(f"{len(model['projects'])} projects exceed the template budget.")
    for entry in model.get("experience") or []:
        if len(entry.get("bullets") or []) > int(budgets.get("bullets_per_role", 5)):
            errors.append(f"A role has {len(entry['bullets'])} bullets; the template allows {budgets.get('bullets_per_role', 5)}.")
    for entry in model.get("projects") or []:
        if len(entry.get("bullets") or []) > int(budgets.get("bullets_per_project", 4)):
            errors.append(f"A project has {len(entry['bullets'])} bullets; the template allows {budgets.get('bullets_per_project', 4)}.")
    skill_count = sum(len(group.get("items") or []) for group in model.get("skills") or [])
    if skill_count > int(budgets.get("max_skills", 16)):
        errors.append(f"{skill_count} skills exceed the template budget of {budgets.get('max_skills', 16)}.")

    if errors:
        raise LayoutError(
            "layout.budget",
            "The selected content exceeds the template budget.",
            fix=" ".join(errors) + " Run `resume tailor` or choose a roomier template.",
        )

    app_budget = application.get("page_budget") or {}
    template_pages = (manifest.get("page") or {}).get("target_pages") or {}
    target = min(
        int(template_pages.get("max", 2)),
        int(app_budget.get("target", 1)) if app_budget.get("target") else 1,
    )
    maximum = min(
        int(template_pages.get("max", 2)),
        int(app_budget.get("max", 2)),
    )
    lines = _content_lines(model)
    pages = max(1, math.ceil(lines / LINES_PER_PAGE))
    if pages > maximum:
        raise LayoutError(
            "layout.page_count",
            f"Estimated {pages} page(s); the application allows at most {maximum}.",
            fix="Cut weaker bullets or roles, or choose a template with a larger budget. Do not shrink below 9pt.",
        )
    warnings = []
    if pages > target:
        warnings.append(f"Estimated {pages} page(s), above the target of {target}.")
    remainder = lines % LINES_PER_PAGE
    bottom = 0 if remainder == 0 else round((LINES_PER_PAGE - remainder) / LINES_PER_PAGE * 100)
    if pages > 1 and bottom > 45:
        warnings.append("The last page looks sparse; tighten or rebalance the content.")
    return LayoutReport(
        pages=pages,
        target_pages=target,
        max_pages=maximum,
        lines=lines,
        bottom_whitespace_pct=bottom,
        warnings=warnings,
    )
