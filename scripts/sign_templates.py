# SPDX-License-Identifier: MIT
"""Validate and sign six baseline layouts in both language folders.

Manifest status is library metadata, not an approval decision. This script never
reads or writes private candidates, approval ledgers, or writing profiles.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from bs4 import BeautifulSoup
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"
SCHEMA = json.loads((ROOT / "schema" / "template.schema.json").read_text(encoding="utf-8"))
NOW = "2026-11-05T00:00:00Z"
LANGUAGES = {"cn": "zh", "en": "en"}
# Informational compatibility only; markets do not select a writing language.
MARKETS = ["intl_en", "cn_internet", "cn_soe", "cn_finance", "cn_creative", "hk_sg", "academic"]
# Provenance only: every ID below is generated in BOTH language folders.
BASELINE_FOLDERS = {
    "ats-classic": "en", "campus": "cn", "modern-sidebar": "en",
    "editorial": "en", "executive": "en", "zh-professional": "cn",
}


def slot(name: str, kind: str, *, repeatable: bool = False) -> dict:
    value = {"name": name, "selector": f"[data-slot='{name}']", "kind": kind}
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

# Geometry, slots, and budgets belong to layouts, never to languages or markets.
# Personas remain layout hints, not writing rules.
CONFIG = {
    "ats-classic": {
        "name": {"zh": "ATS 经典", "en": "ATS Classic"},
        "description": "Single-column, standard headings, no graphics. Parseability-first.",
        "personas": ["experienced", "new_grad", "student_with_internship", "student_with_projects", "career_switcher"],
        "page": {
            "sizes": ["a4"],
            "margins_mm": {"top": 18, "right": 18, "bottom": 18, "left": 18},
            "target_pages": {"min": 1, "max": 2}, "columns": "single",
        },
        "required": [
            ("identity.name", "text"), ("identity.contact", "text"),
            ("section.education", "section"), ("section.experience", "section"),
            ("section.skills", "section"),
        ],
        "optional": [
            ("identity.links", "list"), ("identity.photo", "image"),
            ("section.summary", "rich_text"), ("section.projects", "section"),
            ("section.awards", "section"), ("section.certificates", "section"),
            ("section.languages", "section"), ("section.publications", "section"),
            ("section.open_source", "section"), *COMMON_ITEM_SLOTS,
        ],
        "budgets": {
            "summary_chars": {"en": 240, "zh": 120}, "bullets_per_role": 5,
            "bullets_per_project": 4, "max_roles": 5, "max_projects": 4, "max_skills": 16,
        },
        "ats": {"single_column": True, "text_selectable": True, "tables_allowed": False},
    },
    "campus": {
        "name": {"zh": "校园", "en": "Campus"},
        "description": "Education-first resume with visible fundamentals, A4, 1–2 pages; no job-intent section.",
        "personas": ["student_with_projects", "student_with_internship", "new_grad", "experienced", "career_switcher", "senior_manager"],
        "page": {
            "sizes": ["a4"],
            "margins_mm": {"top": 16, "right": 16, "bottom": 16, "left": 16},
            "target_pages": {"min": 1, "max": 2}, "columns": "single",
        },
        "required": [
            ("identity.name", "text"), ("identity.contact", "text"),
            ("section.education", "section"), ("section.skills", "section"),
        ],
        "optional": [
            ("identity.links", "list"), ("identity.photo", "image"),
            ("section.experience", "section"), ("section.projects", "section"),
            ("section.awards", "section"), ("section.open_source", "section"),
            ("section.certificates", "section"), ("section.languages", "section"),
            ("section.publications", "section"), ("section.summary", "rich_text"),
            *COMMON_ITEM_SLOTS,
        ],
        "budgets": {
            "summary_chars": {"en": 240, "zh": 120}, "bullets_per_role": 4,
            "bullets_per_project": 3, "max_roles": 4, "max_projects": 3, "max_skills": 12,
        },
        "ats": {"single_column": True, "text_selectable": True, "tables_allowed": False},
    },
    "modern-sidebar": {
        "name": {"zh": "现代侧栏", "en": "Modern Sidebar"},
        "description": "Restrained two-column layout with a logical DOM order and a single-column screen fallback.",
        "personas": ["experienced", "career_switcher"],
        "page": {
            "sizes": ["a4"],
            "margins_mm": {"top": 16, "right": 16, "bottom": 16, "left": 16},
            "target_pages": {"min": 1, "max": 2}, "columns": "main_sidebar",
        },
        "required": [
            ("identity.name", "text"), ("identity.contact", "text"),
            ("section.summary", "rich_text"), ("section.experience", "section"),
            ("section.skills", "section"), ("section.education", "section"),
        ],
        "optional": [
            ("identity.links", "list"), ("identity.photo", "image"),
            ("section.projects", "section"), ("section.awards", "section"),
            ("section.certificates", "section"), ("section.languages", "section"),
            ("section.publications", "section"), ("section.open_source", "section"),
            *COMMON_ITEM_SLOTS,
        ],
        "budgets": {
            "summary_chars": {"en": 240, "zh": 120}, "bullets_per_role": 5,
            "bullets_per_project": 4, "max_roles": 5, "max_projects": 4, "max_skills": 16,
        },
        "ats": {"single_column": False, "text_selectable": True, "tables_allowed": False},
    },
    "editorial": {
        "name": {"zh": "编辑风格", "en": "Editorial"},
        "description": "One-page editorial layout for early-career candidates; projects lead.",
        "personas": ["student_with_projects", "new_grad", "student_with_internship", "career_switcher"],
        "page": {
            "sizes": ["a4"],
            "margins_mm": {"top": 18, "right": 18, "bottom": 18, "left": 18},
            "target_pages": {"min": 1, "max": 1}, "columns": "single",
        },
        "required": [
            ("identity.name", "text"), ("identity.contact", "text"),
            ("section.summary", "rich_text"), ("section.projects", "section"),
            ("section.education", "section"),
        ],
        "optional": [
            ("identity.links", "list"), ("identity.photo", "image"),
            ("section.experience", "section"), ("section.skills", "section"),
            ("section.awards", "section"), ("section.certificates", "section"),
            ("section.languages", "section"), ("section.publications", "section"),
            ("section.open_source", "section"), *COMMON_ITEM_SLOTS,
        ],
        "budgets": {
            "summary_chars": {"en": 240, "zh": 120}, "bullets_per_role": 4,
            "bullets_per_project": 3, "max_roles": 3, "max_projects": 3, "max_skills": 12,
        },
        "ats": {"single_column": True, "text_selectable": True, "tables_allowed": False},
    },
    "executive": {
        "name": {"zh": "高管", "en": "Executive"},
        "description": "Two-page senior/manager resume; outcome-first and scope-forward.",
        "personas": ["senior_manager", "experienced"],
        "page": {
            "sizes": ["a4"],
            "margins_mm": {"top": 18, "right": 18, "bottom": 18, "left": 18},
            "target_pages": {"min": 2, "max": 2}, "columns": "single",
        },
        "required": [
            ("identity.name", "text"), ("identity.contact", "text"),
            ("section.summary", "rich_text"), ("section.experience", "section"),
            ("section.education", "section"),
        ],
        "optional": [
            ("identity.links", "list"), ("identity.photo", "image"),
            ("section.projects", "section"), ("section.skills", "section"),
            ("section.awards", "section"), ("section.certificates", "section"),
            ("section.languages", "section"), ("section.publications", "section"),
            ("section.open_source", "section"), *COMMON_ITEM_SLOTS,
        ],
        "budgets": {
            "summary_chars": {"en": 240, "zh": 120}, "bullets_per_role": 6,
            "bullets_per_project": 4, "max_roles": 7, "max_projects": 4, "max_skills": 20,
        },
        "ats": {"single_column": True, "text_selectable": True, "tables_allowed": False},
    },
    "zh-professional": {
        "name": {"zh": "专业侧栏", "en": "Professional Sidebar"},
        "description": "Professional sidebar resume: experience-first main column, A4, 2–3 pages.",
        "personas": ["experienced", "career_switcher", "senior_manager"],
        "page": {
            "sizes": ["a4"],
            "margins_mm": {"top": 16, "right": 16, "bottom": 16, "left": 16},
            "target_pages": {"min": 2, "max": 3}, "columns": "sidebar_main",
        },
        "required": [
            ("identity.name", "text"), ("identity.contact", "text"),
            ("section.summary", "rich_text"), ("section.experience", "section"),
            ("section.education", "section"), ("section.skills", "section"),
        ],
        "optional": [
            ("identity.links", "list"), ("identity.photo", "image"),
            ("section.projects", "section"), ("section.awards", "section"),
            ("section.certificates", "section"), ("section.languages", "section"),
            ("section.publications", "section"), ("section.open_source", "section"),
            *COMMON_ITEM_SLOTS,
        ],
        "budgets": {
            "summary_chars": {"en": 240, "zh": 120}, "bullets_per_role": 5,
            "bullets_per_project": 4, "max_roles": 6, "max_projects": 4, "max_skills": 16,
        },
        "ats": {"single_column": False, "text_selectable": True, "tables_allowed": False},
    },
}


def build(template_id: str, config: dict, *, folder: str) -> None:
    language = LANGUAGES[folder]
    directory = TEMPLATES / folder / template_id
    html_text = (directory / "template.html").read_text(encoding="utf-8")
    css_text = (directory / "styles.css").read_text(encoding="utf-8")
    soup = BeautifulSoup(html_text, "html.parser")
    headings = [heading.get_text(" ", strip=True) for heading in soup.select("section h2")]
    if not soup.html or soup.html.get("lang") != language or not headings or not all(headings):
        raise SystemExit(f"{folder}/{template_id}: missing headings or incorrect HTML language")
    fingerprint = hashlib.sha256((html_text + "\n" + css_text).encode("utf-8")).hexdigest()
    manifest_path = directory / "manifest.json"
    baseline_folder = BASELINE_FOLDERS[template_id]
    metadata_path = manifest_path if manifest_path.exists() else TEMPLATES / baseline_folder / template_id / "manifest.json"
    previous = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
    provenance = previous.get("provenance", {
        "kind": "original",
        "note": "Original layout; informed by public resume guidance, not copied from another template.",
    })
    if not manifest_path.exists() and folder != baseline_folder:
        provenance = {
            "kind": provenance["kind"],
            "note": f"Language counterpart of the original templates/{baseline_folder}/{template_id} baseline; "
                    "preserves its structure with localized headings and typography. No approval or promotion implied.",
        }
    manifest = {
        "id": template_id,
        "name": config["name"][language],
        "language": language,
        "version": previous.get("version", "1.0.0"),
        "status": previous.get("status", "stable"),
        "description": config["description"],
        "markets": MARKETS,
        "personas": config["personas"],
        "page": config["page"],
        "slots": {
            "required": [slot(name, kind) for name, kind in config["required"]],
            "optional": [slot(name, kind, repeatable=kind == "list") for name, kind in config["optional"]],
        },
        "budgets": config["budgets"],
        "files": {"html": "template.html", "css": "styles.css", "preview": "preview.html", "print_css": "styles.css"},
        "print": {"safe_margin_mm": 12, "bleed_mm": 0, "color_mode": "grayscale_safe"},
        "ats": {**config["ats"], "standard_headings": headings},
        "editable_variant": True,
        "fingerprint": fingerprint,
        "created_at": previous.get("created_at", NOW),
        "provenance": provenance,
    }
    errors = sorted(Draft202012Validator(SCHEMA).iter_errors(manifest), key=lambda e: str(list(e.path)))
    if errors:
        first = errors[0]
        raise SystemExit(f"{folder}/{template_id}: {list(first.path)} {first.message}")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("validated and signed", f"{folder}/{template_id}", fingerprint[:12])


def main() -> None:
    for folder in LANGUAGES:
        for template_id, config in CONFIG.items():
            build(template_id, config, folder=folder)


if __name__ == "__main__":
    main()
