# SPDX-License-Identifier: MIT
"""Generate and sign the three library template manifests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"
SCHEMA = json.loads((ROOT / "schema" / "template.schema.json").read_text(encoding="utf-8"))
NOW = "2026-11-05T00:00:00Z"


def slot(name: str, kind: str, *, repeatable: bool = False) -> dict:
    value = {
        "name": name,
        "selector": f"[data-slot='{name}']",
        "kind": kind,
    }
    if repeatable:
        value["repeatable"] = True
    return value


COMMON_ITEM_SLOTS = [
    ("education.item", "list"),
    ("experience.item", "list"),
    ("experience.item.bullet", "list"),
    ("project.item", "list"),
    ("project.item.bullet", "list"),
]

CONFIG = {
    "ats-classic": {
        "name": "ATS Classic",
        "language": "en",
        "description": "Single-column, standard headings, no graphics. Parseability-first.",
        "markets": ["intl_en"],
        "personas": ["experienced", "new_grad", "student_with_internship", "student_with_projects", "career_switcher"],
        "page": {
            "sizes": ["a4"],
            "margins_mm": {"top": 18, "right": 18, "bottom": 18, "left": 18},
            "target_pages": {"min": 1, "max": 2},
            "columns": "single",
        },
        "required": [
            ("identity.name", "text"),
            ("identity.contact", "text"),
            ("section.education", "section"),
            ("section.experience", "section"),
            ("section.skills", "section"),
        ],
        "optional": [
            ("identity.links", "list"),
            ("identity.photo", "image"),
            ("section.summary", "rich_text"),
            ("section.projects", "section"),
            ("section.awards", "section"),
            ("section.certificates", "section"),
            ("section.languages", "section"),
            ("section.publications", "section"),
            ("section.open_source", "section"),
            *COMMON_ITEM_SLOTS,
        ],
        "budgets": {
            "summary_chars": {"en": 240, "zh": 120},
            "bullets_per_role": 5,
            "bullets_per_project": 4,
            "max_roles": 5,
            "max_projects": 4,
            "max_skills": 16,
        },
        "ats": {
            "single_column": True,
            "text_selectable": True,
            "tables_allowed": False,
            "standard_headings": ["Summary", "Experience", "Projects", "Skills", "Education", "Awards"],
        },
    },
    "campus": {
        "name": "Campus",
        "language": "zh",
        "description": "CN campus resume: education first, fundamentals visible, A4, 1–2 pages; no job-intent section.",
        "markets": ["cn_internet", "cn_soe", "cn_finance", "cn_creative"],
        "personas": [
            "student_with_projects",
            "student_with_internship",
            "new_grad",
            "experienced",
            "career_switcher",
            "senior_manager",
        ],
        "page": {
            "sizes": ["a4"],
            "margins_mm": {"top": 16, "right": 16, "bottom": 16, "left": 16},
            "target_pages": {"min": 1, "max": 2},
            "columns": "single",
        },
        "required": [
            ("identity.name", "text"),
            ("identity.contact", "text"),
            ("section.education", "section"),
            ("section.skills", "section"),
        ],
        "optional": [
            ("identity.links", "list"),
            ("identity.photo", "image"),
            ("section.experience", "section"),
            ("section.projects", "section"),
            ("section.awards", "section"),
            ("section.open_source", "section"),
            ("section.certificates", "section"),
            ("section.languages", "section"),
            ("section.publications", "section"),
            ("section.summary", "rich_text"),
            *COMMON_ITEM_SLOTS,
        ],
        "budgets": {
            "summary_chars": {"en": 240, "zh": 120},
            "bullets_per_role": 4,
            "bullets_per_project": 3,
            "max_roles": 4,
            "max_projects": 3,
            "max_skills": 12,
        },
        "ats": {
            "single_column": True,
            "text_selectable": True,
            "tables_allowed": False,
            "standard_headings": ["教育经历", "专业技能", "实习经历", "项目经历", "荣誉奖项"],
        },
    },
    "modern-sidebar": {
        "name": "Modern Sidebar",
        "language": "en",
        "description": "Restrained two-column layout with a logical DOM order and a single-column screen fallback.",
        "markets": ["intl_en"],
        "personas": ["experienced", "career_switcher"],
        "page": {
            "sizes": ["a4"],
            "margins_mm": {"top": 16, "right": 16, "bottom": 16, "left": 16},
            "target_pages": {"min": 1, "max": 2},
            "columns": "main_sidebar",
        },
        "required": [
            ("identity.name", "text"),
            ("identity.contact", "text"),
            ("section.summary", "rich_text"),
            ("section.experience", "section"),
            ("section.skills", "section"),
            ("section.education", "section"),
        ],
        "optional": [
            ("identity.links", "list"),
            ("identity.photo", "image"),
            ("section.projects", "section"),
            ("section.awards", "section"),
            ("section.certificates", "section"),
            ("section.languages", "section"),
            ("section.publications", "section"),
            ("section.open_source", "section"),
            *COMMON_ITEM_SLOTS,
        ],
        "budgets": {
            "summary_chars": {"en": 240, "zh": 120},
            "bullets_per_role": 5,
            "bullets_per_project": 4,
            "max_roles": 5,
            "max_projects": 4,
            "max_skills": 16,
        },
        "ats": {
            "single_column": False,
            "text_selectable": True,
            "tables_allowed": False,
            "standard_headings": ["Summary", "Experience", "Projects", "Skills", "Education"],
        },
    },


    "editorial": {
        "name": "Editorial",
        "language": "en",
        "description": "One-page editorial layout for early-career candidates; projects lead.",
        "markets": ["intl_en"],
        "personas": ["student_with_projects", "new_grad", "student_with_internship", "career_switcher"],
        "page": {
            "sizes": ["a4"],
            "margins_mm": {"top": 18, "right": 18, "bottom": 18, "left": 18},
            "target_pages": {"min": 1, "max": 1},
            "columns": "single",
        },
        "required": [
            ("identity.name", "text"),
            ("identity.contact", "text"),
            ("section.summary", "rich_text"),
            ("section.projects", "section"),
            ("section.education", "section"),
        ],
        "optional": [
            ("identity.links", "list"),
            ("identity.photo", "image"),
            ("section.experience", "section"),
            ("section.skills", "section"),
            ("section.awards", "section"),
            ("section.certificates", "section"),
            ("section.languages", "section"),
            ("section.publications", "section"),
            ("section.open_source", "section"),
            *COMMON_ITEM_SLOTS,
        ],
        "budgets": {
            "summary_chars": {"en": 240, "zh": 120},
            "bullets_per_role": 4,
            "bullets_per_project": 3,
            "max_roles": 3,
            "max_projects": 3,
            "max_skills": 12,
        },
        "ats": {
            "single_column": True,
            "text_selectable": True,
            "tables_allowed": False,
            "standard_headings": ["Summary", "Selected Projects", "Experience", "Skills", "Education"],
        },
    },
    "executive": {
        "name": "Executive",
        "language": "en",
        "description": "Two-page senior/manager resume; outcome-first and scope-forward.",
        "markets": ["intl_en"],
        "personas": ["senior_manager", "experienced"],
        "page": {
            "sizes": ["a4"],
            "margins_mm": {"top": 18, "right": 18, "bottom": 18, "left": 18},
            "target_pages": {"min": 2, "max": 2},
            "columns": "single",
        },
        "required": [
            ("identity.name", "text"),
            ("identity.contact", "text"),
            ("section.summary", "rich_text"),
            ("section.experience", "section"),
            ("section.education", "section"),
        ],
        "optional": [
            ("identity.links", "list"),
            ("identity.photo", "image"),
            ("section.projects", "section"),
            ("section.skills", "section"),
            ("section.awards", "section"),
            ("section.certificates", "section"),
            ("section.languages", "section"),
            ("section.publications", "section"),
            ("section.open_source", "section"),
            *COMMON_ITEM_SLOTS,
        ],
        "budgets": {
            "summary_chars": {"en": 240, "zh": 120},
            "bullets_per_role": 6,
            "bullets_per_project": 4,
            "max_roles": 7,
            "max_projects": 4,
            "max_skills": 20,
        },
        "ats": {
            "single_column": True,
            "text_selectable": True,
            "tables_allowed": False,
            "standard_headings": ["Executive Summary", "Experience", "Leadership & Skills", "Education"],
        },
    },

    "zh-professional": {
        "name": "Chinese Professional",
        "language": "zh",
        "description": "Chinese professional resume: experience-first, Chinese typography, A4, 2–3 pages.",
        "markets": ["cn_internet", "cn_soe", "cn_finance", "cn_creative"],
        "personas": ["experienced", "career_switcher", "senior_manager"],
        "page": {
            "sizes": ["a4"],
            "margins_mm": {"top": 16, "right": 16, "bottom": 16, "left": 16},
            "target_pages": {"min": 2, "max": 3},
            "columns": "sidebar_main",
        },
        "required": [
            ("identity.name", "text"),
            ("identity.contact", "text"),
            ("section.summary", "rich_text"),
            ("section.experience", "section"),
            ("section.education", "section"),
            ("section.skills", "section"),
        ],
        "optional": [
            ("identity.links", "list"),
            ("identity.photo", "image"),
            ("section.summary", "rich_text"),
            ("section.projects", "section"),
            ("section.awards", "section"),
            ("section.certificates", "section"),
            ("section.languages", "section"),
            ("section.publications", "section"),
            ("section.open_source", "section"),
            *COMMON_ITEM_SLOTS,
        ],
        "budgets": {
            "summary_chars": {"en": 240, "zh": 120},
            "bullets_per_role": 5,
            "bullets_per_project": 4,
            "max_roles": 6,
            "max_projects": 4,
            "max_skills": 16,
        },
        "ats": {
            "single_column": True,
            "text_selectable": True,
            "tables_allowed": False,
            "standard_headings": ["个人简介", "工作经历", "项目经历", "专业技能", "教育经历", "荣誉奖项"],
        },
    },




}


def build(template_id: str, config: dict) -> None:
    folder = "cn" if config["language"] == "zh" else "en"
    directory = TEMPLATES / folder / template_id
    html_text = (directory / "template.html").read_text(encoding="utf-8")
    css_text = (directory / "styles.css").read_text(encoding="utf-8")
    fingerprint = hashlib.sha256((html_text + "\n" + css_text).encode("utf-8")).hexdigest()
    manifest = {
        "id": template_id,
        "name": config["name"],
        "language": config["language"],
        "version": "1.0.0",
        "status": "stable",
        "description": config["description"],
        "markets": config["markets"],
        "personas": config["personas"],
        "page": config["page"],
        "slots": {
            "required": [slot(name, kind) for name, kind in config["required"]],
            "optional": [
                slot(name, kind, repeatable=kind == "list") for name, kind in config["optional"]
            ],
        },
        "budgets": config["budgets"],
        "files": {
            "html": "template.html",
            "css": "styles.css",
            "preview": "preview.html",
            "print_css": "styles.css",
        },
        "print": {"safe_margin_mm": 12, "bleed_mm": 0, "color_mode": "grayscale_safe"},
        "ats": config["ats"],
        "editable_variant": True,
        "fingerprint": fingerprint,
        "created_at": NOW,
        "provenance": {
            "kind": "original",
            "note": "Original layout; informed by public resume guidance, not copied from another template.",
        },
    }
    errors = sorted(Draft202012Validator(SCHEMA).iter_errors(manifest), key=lambda e: list(e.path))
    if errors:
        first = errors[0]
        raise SystemExit(f"{template_id}: {list(first.path)} {first.message}")
    (directory / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("signed", template_id, fingerprint[:12])


for template_id, config in CONFIG.items():
    build(template_id, config)
