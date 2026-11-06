# SPDX-License-Identifier: MIT
"""Content linter: global rules plus Chinese-market rules."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from . import profile
from .application import page_budget
from .skim import SkimResult, skim_test

AI_TERMS = re.compile(
    r"\b(ai|llm|rag|aigc|agent|prompt|transformer|deep learning|machine learning|nlp|cv)\b|大模型|人工智能|机器学习|深度学习|检索增强",
    re.IGNORECASE,
)
WEAK_START = re.compile(
    r"^(worked on|responsible for|helped|participated in|assisted|involved in|负责|参与|协助|配合)",
    re.IGNORECASE,
)
SUPERLATIVES = re.compile(
    r"\b(best|world-class|cutting-edge|revolutionary|unparalleled)\b|第一|顶尖|颠覆|革命性",
    re.IGNORECASE,
)
CLICHES = (
    "具有良好的沟通能力",
    "团队合作精神",
    "学习能力强",
    "吃苦耐劳",
    "责任心强",
    "积极主动",
    "熟练掌握",
    "精通",
    "passionate about",
    "team player",
    "hard-working",
    "detail-oriented",
    "self-starter",
    "excellent communication skills",
)
PLACEHOLDER_RE = re.compile(r"example\.com|your-domain|yourdomain|xxx|todo|placeholder", re.IGNORECASE)
FIRST_PERSON = re.compile(r"^(i|my)\b|我的|本人", re.IGNORECASE)


@dataclass
class LintIssue:
    code: str
    severity: str  # error | warn | info
    path: str
    message: str
    fix: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "path": self.path,
            "message": self.message,
            "fix": self.fix,
        }


@dataclass
class LintReport:
    issues: list[LintIssue]
    skim: SkimResult
    page_estimate: int
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def errors(self) -> list[LintIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[LintIssue]:
        return [i for i in self.issues if i.severity == "warn"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "page_estimate": self.page_estimate,
            "counts": self.counts,
            "skim": self.skim.to_dict(),
            "issues": [i.to_dict() for i in self.issues],
            "errors": [i.to_dict() for i in self.errors],
            "warnings": [i.to_dict() for i in self.warnings],
        }


def _text(bullet: dict[str, Any]) -> str:
    return " ".join(str(v) for v in (bullet.get("text") or {}).values() if v)


def _has_digit(text: str) -> bool:
    return bool(re.search(r"\d", text))


def _iter_bullets(vault: dict[str, Any]):
    for collection in ("experience", "projects"):
        for index, item in enumerate(vault.get(collection) or []):
            for b_index, bullet in enumerate(item.get("bullets") or []):
                yield f"{collection}[{index}].bullets[{b_index}]", bullet, item


def _summary_text(vault: dict[str, Any]) -> str:
    summary = (vault.get("identity") or {}).get("summary") or {}
    if isinstance(summary, dict):
        return " ".join(str(v) for v in summary.values() if v)
    return str(summary or "")


def _estimate_pages(vault: dict[str, Any], application: dict[str, Any] | None) -> int:
    lines = 4.0
    lines += len(_summary_text(vault)) / 70
    lines += len(vault.get("education") or []) * 3
    for role in vault.get("experience") or []:
        lines += 3 + len(role.get("bullets") or []) * 1.7
    for project in vault.get("projects") or []:
        lines += 2 + len(project.get("bullets") or []) * 1.7
    skill_count = sum(len(group.get("items") or []) for group in vault.get("skills") or [])
    lines += max(1, skill_count / 6)
    lines += len(vault.get("awards") or []) * 0.5
    return max(1, math.ceil(lines / 45))


def lint(
    vault: dict[str, Any],
    *,
    market: str,
    persona: str,
    application: dict[str, Any] | None = None,
    target_role: str | None = None,
) -> LintReport:
    issues: list[LintIssue] = []
    is_cn = market.startswith("cn_")
    is_student = profile.is_student(persona)
    budget = (application or {}).get("page_budget") or page_budget(market, persona)
    summary = _summary_text(vault)
    registry = vault.get("evidence") or {}
    all_skills = [
        str(item.get("name", ""))
        for group in vault.get("skills") or []
        for item in group.get("items") or []
    ]
    skills_text = " ".join(all_skills)
    fundamentals = any(group.get("kind") == "fundamentals" for group in vault.get("skills") or [])
    ai_mentions = len(AI_TERMS.findall(skills_text + " " + summary + " " + " ".join(_text(b) for _, b, _ in _iter_bullets(vault))))

    def add(code: str, severity: str, path: str, message: str, fix: str = "") -> None:
        issues.append(LintIssue(code, severity, path, message, fix))

    if not vault.get("education"):
        add(
            "cn.structure_missing_education" if is_cn else "lint.missing_education",
            "error",
            "education",
            "Education is missing.",
            "Add school, degree, major, and dates; never omit education for parser or HR reasons.",
        )

    for path, bullet, parent in _iter_bullets(vault):
        text = _text(bullet)
        if not text:
            add("lint.empty_bullet", "error", path, "The bullet is empty.", "Remove it or fill it with a real result.")
            continue
        if FIRST_PERSON.search(text):
            add("lint.first_person", "warn", path, "First-person wording is usually unnecessary.", "Start with the action or result, not `I` or `我的`.")
        if WEAK_START.search(text):
            add("lint.weak_verb", "warn", path, "The bullet starts with a weak verb.", "Lead with what you drove, built, cut, or shipped.")
        if not _has_digit(text):
            add("lint.no_metric", "info", path, "The bullet has no number.", "Add a real number if one exists; otherwise keep the verifiable outcome.")
        if len(text) > (140 if is_cn else 240):
            add("lint.bullet_too_long", "warn", path, "The bullet is too long for a skim.", "Cut it to one action and one result.")
        if len(text) < (12 if is_cn else 20):
            add("lint.bullet_thin", "warn", path, "This bullet is too thin to show ability.", "Expand it with a complete action and outcome, or merge it.")
        if SUPERLATIVES.search(text):
            add("lint.unsupported_superlative", "warn", path, "Superlatives without proof are noise.", "Replace the adjective with a specific result.")
        if PLACEHOLDER_RE.search(text):
            add("lint.placeholder_link", "warn", path, "A placeholder URL is present.", "Use the real link or remove it.")
        refs = bullet.get("evidence") or []
        statuses = [registry.get(ref, {}).get("status") for ref in refs]
        if _has_digit(text) and refs and all(status in ("estimated", "unknown") for status in statuses):
            add("lint.unsupported_number", "error", path, "A number is backed only by an estimate.", "Attach a real source or remove the number.")
        if is_cn and WEAK_START.search(text) and not _has_digit(text):
            add("cn.flow_account", "warn", path, "This reads like a duty list, not an owned result.", "Rewrite as: what you owned, what you changed, what happened.")
        if is_cn:
            for phrase in CLICHES:
                if phrase in text:
                    add("cn.cliche", "warn", path, f"Cliché phrase: {phrase}", "Delete it and show the behavior with a fact.")
                    break

    # Summary rules.
    if summary:
        if is_cn and re.match(r"^(本人|作为一名|我是一名)", summary):
            add("cn.cliche_opening", "warn", "identity.summary", "The summary opens with a cliché.", "Open with the strongest fact, not a self-description.")
        if is_cn and "自我评价" in summary:
            add("cn.self_evaluation", "warn", "identity.summary", "Self-evaluation filler is present.", "Replace it with evidence.")
        for phrase in CLICHES:
            if phrase in summary:
                add("cn.cliche", "warn", "identity.summary", f"Cliché phrase: {phrase}", "Delete it and show the behavior with a fact.")
                break

    # CN campus rules.
    if is_cn and is_student:
        if not fundamentals:
            add(
                "cn.cs_fundamentals_missing",
                "error",
                "skills",
                "No CS fundamentals group is present.",
                "Add OS, networks, data structures, algorithms, and databases; campus written tests check them.",
            )
        if ai_mentions >= 5 and fundamentals:
            add(
                "cn.ai_buzzword_density",
                "warn",
                "skills",
                "AI terms outnumber the fundamentals signal.",
                "Keep AI skills that are real and make the CS fundamentals visible.",
            )

    for index, project in enumerate(vault.get("projects") or []):
        context = project.get("context")
        bullets = [_text(bullet) for bullet in project.get("bullets") or []]
        if len(bullets) < 3 or sum(len(text) for text in bullets) < (90 if is_cn else 160):
            add(
                "lint.project_thin",
                "warn",
                f"projects[{index}]",
                "This project reads thin for HR.",
                "Use 3–4 labeled STAR points with substantial real detail, or exclude the project.",
            )
        if is_student and context in {"personal", "course", "competition", "research", "volunteer"}:
            text = " ".join(bullets)
            tech_count = len(project.get("tech") or [])
            if tech_count <= 2 or len(text) < (180 if is_cn else 320):
                add(
                    "lint.project_rescue",
                    "warn",
                    f"projects[{index}]",
                    "This project needs more framework and technical depth.",
                    "Offer the user two choices: remove the project, or expand it with plausible candidate details that the user confirms.",
                )
        if context in {"course", "personal", "open_source"}:
            if not project.get("own_contribution") and not project.get("optimizations"):
                severity = "error" if is_cn and is_student else "warn"
                add(
                    "cn.demo_only_project" if is_cn else "lint.demo_only_project",
                    severity,
                    f"projects[{index}]",
                    "This project has no personal change or optimization.",
                    "Describe what you changed, why, and what happened.",
                )
        for key in ("start", "end"):
            value = project.get(key)
            if isinstance(value, str) and value[:4].isdigit() and int(value[:4]) > datetime.now().year + 7:
                add("lint.date_future", "warn", f"projects[{index}].{key}", "The date is far in the future.", "Confirm the date.")

    for index, role in enumerate(vault.get("experience") or []):
        start = role.get("start")
        end = role.get("end")
        if isinstance(start, str) and isinstance(end, str) and end not in {"present", ""}:
            if end < start:
                add("lint.date_order", "error", f"experience[{index}]", "The end date is before the start date.", "Fix the dates.")
        if isinstance(start, str) and start[:4].isdigit() and int(start[:4]) > datetime.now().year + 1:
            add("lint.date_future", "warn", f"experience[{index}].start", "The start date is in the future.", "Confirm the date.")

    for section in ("education", "experience", "projects"):
        for index, item in enumerate(vault.get(section) or []):
            if item.get("end") == "present":
                add(
                    "lint.date_open",
                    "warn",
                    f"{section}[{index}].end",
                    "This period ends with 至今/Present.",
                    "Ask for a concrete end month before delivery.",
                )

    for link in (vault.get("identity") or {}).get("links") or []:
        url = str(link.get("url") or "")
        if PLACEHOLDER_RE.search(url) or url in {"#", ""}:
            add(
                "cn.dead_link" if is_cn else "lint.placeholder_link",
                "warn",
                "identity.links",
                f"Placeholder link: {url}",
                "Use the real link or remove it.",
            )

    # Page estimate.
    pages = _estimate_pages(vault, application)
    maximum = int(budget.get("max", 2))
    target = int(budget.get("target", maximum))
    if pages > maximum:
        add(
            "cn.page_count" if is_cn else "lint.page_count",
            "error",
            "page_budget",
            f"Estimated {pages} page(s), above the maximum of {maximum}.",
            "Cut weaker bullets or roles; do not shrink the font below 9pt.",
        )
    elif pages > target:
        add(
            "cn.page_count" if is_cn else "lint.page_count",
            "warn",
            "page_budget",
            f"Estimated {pages} page(s), above the target of {target}.",
            "Tighten the content or accept the larger budget deliberately.",
        )

    # Primacy and structure.
    if application:
        sections = application.get("selection", {}).get("sections") or []
        enabled = [section["id"] for section in sorted(sections, key=lambda s: s["order"]) if section.get("enabled")]
        if is_cn and is_student and "education" in enabled and enabled.index("education") > 2:
            add("cn.primacy", "warn", "selection.sections", "Education is not in the first screen.", "Move education earlier for a CN campus resume.")
        ids = [section["id"] for section in sections]
        if len(ids) != len(set(ids)):
            add("cn.weird_structure", "warn", "selection.sections", "Duplicate sections are configured.", "Keep one entry per section.")

    skim = skim_test(vault, market, persona)
    if not skim.passed:
        add(
            "lint.skim_failed",
            "warn",
            "skim",
            "A 10-second skim does not find name/contact, education, and two core signals.",
            "Move the strongest signals into the first screen.",
        )

    counts = {
        "errors": sum(1 for i in issues if i.severity == "error"),
        "warnings": sum(1 for i in issues if i.severity == "warn"),
        "info": sum(1 for i in issues if i.severity == "info"),
    }
    return LintReport(issues=issues, skim=skim, page_estimate=pages, counts=counts)
