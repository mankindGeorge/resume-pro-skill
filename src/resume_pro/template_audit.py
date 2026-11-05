# SPDX-License-Identifier: MIT
"""Seven-dimension template audit."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from . import profile
from .ingest import IngestResult

VERDICT_EXCELLENT = "excellent"
VERDICT_GOOD = "good_with_fixes"
VERDICT_REPLACE = "replace"
VERDICT_UNMAINTAINABLE = "unmaintainable"

DIMENSION_LABELS = {
    "parseability": ("Parseability", "可解析性"),
    "structure": ("Structure", "结构完整"),
    "typography": ("Typography", "排版"),
    "layout": ("Layout", "布局"),
    "market_fit": ("Market fit", "市场适配"),
    "print_safety": ("Print safety", "打印安全"),
    "maintainability": ("Maintainability", "可维护性"),
}

PERSONAL_MARKERS = re.compile(
    r"\b(date of birth|birth date|gender|marital status|nationality|age)\b|出生|性别|婚姻|民族|政治面貌|年龄",
    re.IGNORECASE,
)
GENERIC_FONTS = {"sans-serif", "serif", "monospace", "system-ui", "ui-sans-serif", "ui-serif"}


@dataclass
class AuditDimension:
    id: str
    status: str  # pass | warn | fail
    score: float
    detail: str
    fix: str = ""
    hard_fail: bool = False

    def to_dict(self) -> dict[str, Any]:
        label_en, label_zh = DIMENSION_LABELS.get(self.id, (self.id, self.id))
        return {
            "id": self.id,
            "label": label_en,
            "label_zh": label_zh,
            "status": self.status,
            "score": round(self.score, 3),
            "detail": self.detail,
            "fix": self.fix,
            "hard_fail": self.hard_fail,
        }


@dataclass
class TemplateAudit:
    verdict: str
    market: str
    persona: str
    dimensions: list[AuditDimension]
    recommendations: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    @property
    def keep_allowed(self) -> bool:
        return self.verdict in (VERDICT_EXCELLENT, VERDICT_GOOD)

    @property
    def hard_fails(self) -> list[AuditDimension]:
        return [d for d in self.dimensions if d.hard_fail]

    @property
    def warnings(self) -> list[AuditDimension]:
        return [d for d in self.dimensions if d.status == "warn"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "keep_allowed": self.keep_allowed,
            "market": self.market,
            "persona": self.persona,
            "dimensions": [d.to_dict() for d in self.dimensions],
            "hard_fails": [d.to_dict() for d in self.hard_fails],
            "warnings": [d.to_dict() for d in self.warnings],
            "recommendations": self.recommendations,
            "metrics": self.metrics,
        }


def _dimension(
    dim_id: str,
    failures: list[str],
    warnings: list[str],
    *,
    fail_fix: str = "",
    warn_fix: str = "",
    hard_fail: bool = False,
) -> AuditDimension:
    if failures:
        return AuditDimension(dim_id, "fail", 0.0, " ".join(failures), fail_fix, hard_fail=hard_fail)
    if warnings:
        return AuditDimension(dim_id, "warn", 0.6, " ".join(warnings), warn_fix)
    return AuditDimension(dim_id, "pass", 1.0, "Pass.")


def audit_template(result: IngestResult, *, market: str, persona: str) -> TemplateAudit:
    layout = result.layout
    fields = result.fields or {}
    text = result.text or ""
    text_len = len(text.strip())
    education = fields.get("education") or []
    experience = fields.get("experience") or []
    projects = fields.get("projects") or []
    skills = fields.get("skills") or []
    has_education = bool(education and education[0].get("school"))
    has_proof = bool(experience or projects)
    has_contact = bool(fields.get("email") or fields.get("phone"))
    has_name = bool(fields.get("name"))
    font_families = [f for f in layout.font_families if f.strip().lower() not in GENERIC_FONTS]
    font_families = list(dict.fromkeys(f.lower() for f in font_families))
    margins = [v for v in layout.margins_mm.values() if v is not None]
    min_margin = min(margins) if margins else None
    page_size = layout.page_size or ("a4" if market == "cn_internet" else "letter")

    # 1. Parseability ------------------------------------------------------
    parse_fail: list[str] = []
    parse_warn: list[str] = []
    if result.scanned:
        parse_fail.append("The file is scanned or image-only; text cannot be extracted.")
    if text_len < 200:
        parse_fail.append(f"Only {text_len} characters were extracted.")
    if text_len >= 200 and not (education or experience or projects):
        parse_fail.append("No education, experience, or project section could be recognized.")
    if result.format in {"md", "markdown", "txt"}:
        parse_warn.append("Plain text has no layout, so structural parsing is heuristic.")
    if layout.columns >= 2 and layout.absolute_positioned:
        parse_warn.append("Two columns plus absolute positioning can scramble the reading order.")
    if layout.images and text_len < 500:
        parse_warn.append("Images exist and little text was extracted; some content may be in images.")
    parseability = _dimension(
        "parseability",
        parse_fail,
        parse_warn,
        fail_fix="Export a text-based DOCX/PDF/HTML, or paste the content as text.",
        warn_fix="Keep a single reading order in the DOM and avoid text in images.",
        hard_fail=bool(parse_fail),
    )

    # 2. Structure ---------------------------------------------------------
    structure_fail: list[str] = []
    structure_warn: list[str] = []
    if not has_name:
        structure_fail.append("No name could be identified.")
    if not has_contact:
        structure_fail.append("No email or phone could be identified.")
    if not has_education:
        structure_fail.append("Education is missing or unreadable.")
    if not has_proof:
        structure_fail.append("No experience or project section was found.")
    if not skills:
        structure_warn.append("No skills section was found.")
    missing_dates = 0
    for entry in education:
        if not entry.get("start") or not entry.get("end"):
            missing_dates += 1
    for entry in experience:
        if not entry.get("start") or not entry.get("end"):
            missing_dates += 1
    if missing_dates:
        structure_warn.append(f"{missing_dates} entr{'y' if missing_dates == 1 else 'ies'} missing a date.")
    structure = _dimension(
        "structure",
        structure_fail,
        structure_warn,
        fail_fix="Add the missing section or field; never omit education.",
        warn_fix="Complete the dates and add a skills section.",
        hard_fail=bool(structure_fail),
    )

    # 3. Typography --------------------------------------------------------
    typo_fail: list[str] = []
    typo_warn: list[str] = []
    body_size = layout.body_font_size_pt
    if body_size is None:
        typo_warn.append("Body font size could not be determined.")
    elif body_size < 9:
        typo_fail.append(f"Body text is {body_size}pt, below the 9pt floor.")
    elif body_size < 10:
        typo_warn.append(f"Body text is {body_size}pt; 10pt or larger is safer.")
    if len(font_families) > 3:
        typo_fail.append(f"{len(font_families)} font families are used; keep at most two.")
    elif len(font_families) > 2:
        typo_warn.append(f"{len(font_families)} font families are used; two is the usual limit.")
    if layout.line_height is not None and layout.line_height < 1.15:
        typo_warn.append(f"Line height is {layout.line_height}, which is tight.")
    typography = _dimension(
        "typography",
        typo_fail,
        typo_warn,
        fail_fix="Raise body text to at least 9pt and reduce font families.",
        warn_fix="Use 10–10.5pt body text and a line height around 1.3–1.45.",
        hard_fail=bool(typo_fail),
    )

    # 4. Layout ------------------------------------------------------------
    layout_fail: list[str] = []
    layout_warn: list[str] = []
    if min_margin is not None and min_margin < 8:
        layout_fail.append(f"The smallest margin is {min_margin}mm.")
    elif min_margin is not None and min_margin < 12:
        layout_warn.append(f"The smallest margin is {min_margin}mm; 12mm or more is safer.")
    if layout.text_outside_page:
        layout_fail.append(f"{layout.text_outside_page} characters sit outside the page.")
    if layout.absolute_positioned > 10:
        layout_fail.append(f"{layout.absolute_positioned} absolutely positioned blocks make the layout fragile.")
    elif layout.absolute_positioned > 3:
        layout_warn.append(f"{layout.absolute_positioned} absolutely positioned blocks may not print reliably.")
    if layout.overflow_hidden:
        layout_warn.append(f"{layout.overflow_hidden} overflow:hidden rule(s) may clip text.")
    if layout.columns >= 2:
        layout_warn.append("Two-column layout can confuse older ATS parsers.")
    if layout.tables > 2:
        layout_warn.append(f"{layout.tables} tables are used; tables are risky for parsing.")
    layout_dim = _dimension(
        "layout",
        layout_fail,
        layout_warn,
        fail_fix="Fix margins, clipping, and absolute positioning before using this template.",
        warn_fix="Prefer a single column with natural flow.",
        hard_fail=bool(layout_fail),
    )

    # 5. Market fit --------------------------------------------------------
    market_fail: list[str] = []
    market_warn: list[str] = []
    if market == "intl_en" and layout.photo_likely:
        market_fail.append("A photo appears in an intl_en resume.")
    if market == "intl_en" and PERSONAL_MARKERS.search(text):
        market_fail.append("Personal fields (age, gender, marital status, etc.) appear in an intl_en resume.")
    if market == "cn_internet" and page_size == "letter":
        market_warn.append("CN applications normally use A4; this file is Letter.")
    if market in {"cn_soe", "cn_finance"} and not has_education:
        market_fail.append("Education is mandatory for this market.")
    market_fit = _dimension(
        "market_fit",
        market_fail,
        market_warn,
        fail_fix="Remove the photo/personal fields, or switch to a market-appropriate template.",
        warn_fix="Use A4 for CN applications.",
        hard_fail=bool(market_fail),
    )

    # 6. Print safety ------------------------------------------------------
    print_fail: list[str] = []
    print_warn: list[str] = []
    if layout.page_size is None:
        print_warn.append("Page size is not declared.")
    elif layout.page_size == "custom":
        print_warn.append("Page size is not Letter or A4.")
    if min_margin is not None and min_margin < 8:
        print_fail.append(f"Margins are too small to print safely ({min_margin}mm).")
    if layout.text_outside_page:
        print_fail.append("Content is clipped outside the printable page.")
    print_safety = _dimension(
        "print_safety",
        print_fail,
        print_warn,
        fail_fix="Use A4/Letter with margins of at least 12mm and keep content inside the page.",
        warn_fix="Declare A4 or Letter explicitly.",
        hard_fail=bool(print_fail),
    )

    # 7. Maintainability ---------------------------------------------------
    maintain_fail: list[str] = []
    maintain_warn: list[str] = []
    if not layout.editable_source:
        maintain_warn.append("A PDF is not editable; a learned template will be an approximation.")
    if layout.absolute_positioned > 10:
        maintain_fail.append("The layout depends on many absolute-positioned blocks.")
    if layout.tables > 3:
        maintain_warn.append(f"{layout.tables} tables make future edits fragile.")
    if result.format in {"md", "markdown", "txt"}:
        maintain_warn.append("No visual layout exists to preserve.")
    maintainability = _dimension(
        "maintainability",
        maintain_fail,
        maintain_warn,
        fail_fix="Rebuild the layout with normal document flow.",
        warn_fix="Keep an editable DOCX/HTML source for future updates.",
        hard_fail=bool(maintain_fail),
    )

    dimensions = [
        parseability,
        structure,
        typography,
        layout_dim,
        market_fit,
        print_safety,
        maintainability,
    ]

    if result.scanned or text_len < 50:
        verdict = VERDICT_UNMAINTAINABLE
    elif any(d.hard_fail for d in dimensions):
        verdict = VERDICT_REPLACE
    elif any(d.status == "warn" for d in dimensions):
        verdict = VERDICT_GOOD
    elif layout.visual_identity >= 2:
        verdict = VERDICT_EXCELLENT
    else:
        verdict = VERDICT_GOOD

    metrics = {
        "text_characters": text_len,
        "education_entries": len(education),
        "experience_entries": len(experience),
        "project_entries": len(projects),
        "skill_count": len(skills),
        "font_families": font_families,
        "body_font_size_pt": body_size,
        "min_margin_mm": min_margin,
        "columns": layout.columns,
        "images": layout.images,
        "photo_likely": layout.photo_likely,
        "tables": layout.tables,
        "absolute_positioned": layout.absolute_positioned,
        "text_outside_page": layout.text_outside_page,
        "page_size": layout.page_size,
        "visual_identity": layout.visual_identity,
        "editable_source": layout.editable_source,
    }

    return TemplateAudit(
        verdict=verdict,
        market=market,
        persona=persona,
        dimensions=dimensions,
        recommendations=recommend_templates(market, persona, verdict),
        metrics=metrics,
    )


def recommend_templates(market: str, persona: str, verdict: str) -> list[str]:
    if verdict == VERDICT_EXCELLENT:
        return []
    if market == "cn_internet":
        if profile.is_student(persona):
            return ["campus", "ats-classic"]
        return ["ats-classic", "modern-sidebar"]
    if market == "intl_en":
        if persona in {"senior_manager", "experienced"}:
            return ["ats-classic", "executive", "modern-sidebar"]
        return ["ats-classic", "editorial", "modern-sidebar"]
    return ["ats-classic"]
