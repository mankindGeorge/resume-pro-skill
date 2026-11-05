# SPDX-License-Identifier: MIT
"""Deterministic HTML rendering tests."""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import re
from pathlib import Path

import pytest

from resume_pro.application import create_application, page_budget, save_application
from resume_pro.layout import LayoutError
from resume_pro.render import RenderError, load_template, render_application
from resume_pro.select import select_facts


def _app(vault, tmp_path, template, market="intl_en", persona="experienced", role="Senior Backend Engineer"):
    budget = page_budget(market, persona)
    selection = select_facts(vault, market=market, persona=persona, target_role=role, page_max=budget["max"])
    application = create_application(
        vault=vault,
        selection=selection,
        role=role,
        market=market,
        persona=persona,
        framework="result_first",
        company="Example Co",
        template_id=template,
    )
    save_application(tmp_path, application)
    return application


def test_render_ats_classic(experienced_vault, tmp_path):
    application = _app(experienced_vault, tmp_path, "ats-classic")
    result = render_application(tmp_path, experienced_vault, application)
    html = Path(result.html_path).read_text(encoding="utf-8")
    assert "Chen Wei" in html
    assert "Experience" in html
    assert "Education" in html
    assert ":root {" in html
    assert "styles.css" not in html
    assert "<template" not in html
    assert result.layout.pages >= 1
    assert not list(Path(result.html_path).parent.glob("*.pdf"))
    assert not list(Path(result.html_path).parent.glob("*.docx"))


def test_render_campus(student_vault, tmp_path):
    application = _app(
        student_vault,
        tmp_path,
        "campus",
        market="cn_internet",
        persona="student_with_internship",
        role="后端开发工程师（校招）",
    )
    result = render_application(tmp_path, student_vault, application)
    html = Path(result.html_path).read_text(encoding="utf-8")
    assert "Li Ming" in html
    assert "教育经历" in html
    assert "项目经历" in html
    assert "个人简介" not in html
    assert "求职意向" not in html
    assert "size: A4" in html
    assert "width: 210mm" in html


def test_render_modern_sidebar(experienced_vault, tmp_path):
    application = _app(experienced_vault, tmp_path, "modern-sidebar")
    result = render_application(tmp_path, experienced_vault, application)
    html = Path(result.html_path).read_text(encoding="utf-8")
    assert 'class="layout"' in html
    assert 'class="aside"' in html
    assert "Skills" in html


def test_render_editorial(student_projects_vault, tmp_path):
    application = _app(
        student_projects_vault,
        tmp_path,
        "editorial",
        market="intl_en",
        persona="student_with_projects",
        role="Backend Engineer",
    )
    result = render_application(tmp_path, student_projects_vault, application)
    html = Path(result.html_path).read_text(encoding="utf-8")
    assert "Selected Projects" in html
    assert "Course QA with RAG" in html
    assert "--font-heading" in html


def test_render_executive(experienced_vault, tmp_path):
    application = _app(
        experienced_vault,
        tmp_path,
        "executive",
        market="intl_en",
        persona="senior_manager",
        role="Engineering Manager",
    )
    result = render_application(tmp_path, experienced_vault, application)
    html = Path(result.html_path).read_text(encoding="utf-8")
    assert "Executive Summary" in html
    assert "Leadership &amp; Skills" in html or "Leadership & Skills" in html
    assert result.layout.pages == 1  # short sample; a real executive resume can use two pages


def _png(path: Path) -> Path:
    payload = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Zl1sAAAAASUVORK5CYII="
    )
    path.write_bytes(payload)
    return path


def test_photo_is_embedded_and_hidden_when_absent(student_vault, tmp_path):
    photo = _png(tmp_path / "photo.png")
    vault = copy.deepcopy(student_vault)
    vault["identity"]["photo"] = str(photo)
    application = _app(vault, tmp_path, "campus", market="cn_internet", persona="student_with_internship", role="Backend Engineer")
    result = render_application(tmp_path, vault, application)
    html = Path(result.html_path).read_text(encoding="utf-8")
    assert "data:image/png;base64," in html
    assert "<img" in html
    assert re.search(r'<body[^>]*data-photo="true"', html)


def test_photo_slot_is_invisible_without_a_photo(student_vault, tmp_path):
    application = _app(student_vault, tmp_path, "campus", market="cn_internet", persona="student_with_internship", role="Backend Engineer")
    result = render_application(tmp_path, student_vault, application)
    html = Path(result.html_path).read_text(encoding="utf-8")
    assert 'data-slot="identity.photo"' in html
    assert "<img" not in html
    assert not re.search(r'<body[^>]*data-photo="true"', html)


def test_intl_market_suppresses_photo(experienced_vault, tmp_path):
    photo = _png(tmp_path / "photo.png")
    vault = copy.deepcopy(experienced_vault)
    vault["identity"]["photo"] = str(photo)
    application = _app(vault, tmp_path, "ats-classic")
    result = render_application(tmp_path, vault, application)
    html = Path(result.html_path).read_text(encoding="utf-8")
    assert "<img" not in html


def test_missing_photo_file_fails(student_vault, tmp_path):
    vault = copy.deepcopy(student_vault)
    vault["identity"]["photo"] = str(tmp_path / "missing.png")
    application = _app(vault, tmp_path, "campus", market="cn_internet", persona="student_with_internship", role="Backend Engineer")
    with pytest.raises(RenderError) as error:
        render_application(tmp_path, vault, application)
    assert error.value.code == "render.photo_missing"


def test_html_escaping(student_vault, tmp_path):
    vault = copy.deepcopy(student_vault)
    vault["experience"][0]["bullets"][0]["text"]["en"] = "<script>alert(1)</script> cut latency by 40%"
    vault["experience"][0]["bullets"][0]["text"]["zh"] = "<script>alert(1)</script> 将延迟降低 40%"
    application = _app(vault, tmp_path, "campus", market="cn_internet", persona="student_with_internship", role="Backend Engineer")
    result = render_application(tmp_path, vault, application)
    html = Path(result.html_path).read_text(encoding="utf-8")
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<script>alert" not in html


def test_draft_banner(student_vault, tmp_path):
    application = _app(student_vault, tmp_path, "campus", market="cn_internet", persona="student_with_internship", role="Backend Engineer")
    result = render_application(tmp_path, student_vault, application, draft=True)
    html = Path(result.html_path).read_text(encoding="utf-8")
    assert "DRAFT — NOT FOR SUBMISSION" in html
    assert 'data-draft="true"' in html


def test_editable_variant(student_vault, tmp_path):
    application = _app(student_vault, tmp_path, "campus", market="cn_internet", persona="student_with_internship", role="Backend Engineer")
    result = render_application(tmp_path, student_vault, application)
    editable = Path(result.editable_path).read_text(encoding="utf-8")
    assert "EDITABLE PREVIEW" in editable
    assert 'contenteditable="true"' in editable
    assert "not merged back" in editable


def test_byte_stable(student_vault, tmp_path):
    application = _app(student_vault, tmp_path, "campus", market="cn_internet", persona="student_with_internship", role="Backend Engineer")
    first = render_application(tmp_path, student_vault, application)
    first_bytes = Path(first.html_path).read_bytes()
    second = render_application(tmp_path, student_vault, application)
    second_bytes = Path(second.html_path).read_bytes()
    assert first_bytes == second_bytes
    assert hashlib.sha256(first_bytes).hexdigest() == hashlib.sha256(second_bytes).hexdigest()


def test_page_size_mismatch(experienced_vault, tmp_path):
    application = _app(experienced_vault, tmp_path, "ats-classic")
    application["page_budget"]["size"] = "letter"
    with pytest.raises(RenderError) as error:
        render_application(tmp_path, experienced_vault, application)
    assert error.value.code == "render.page_size_mismatch"


def test_language_mismatch_is_rejected(student_vault, experienced_vault, tmp_path):
    cn_app = _app(student_vault, tmp_path, "ats-classic", market="cn_internet", persona="student_with_internship", role="Backend Engineer")
    with pytest.raises(RenderError) as error:
        render_application(tmp_path, student_vault, cn_app)
    assert error.value.code == "render.language_mismatch"
    en_app = _app(experienced_vault, tmp_path, "campus", market="intl_en", persona="experienced", role="Senior Backend Engineer")
    with pytest.raises(RenderError) as error:
        render_application(tmp_path, experienced_vault, en_app)
    assert error.value.code == "render.language_mismatch"


def test_render_zh_professional(experienced_vault, tmp_path):
    application = _app(
        experienced_vault,
        tmp_path,
        "zh-professional",
        market="cn_internet",
        persona="experienced",
        role="高级后端工程师",
    )
    result = render_application(tmp_path, experienced_vault, application)
    html = Path(result.html_path).read_text(encoding="utf-8")
    assert "工作经历" in html
    assert "教育经历" in html
    assert "求职意向" not in html
    assert "size: A4" in html


def test_layout_budget_error(student_vault, tmp_path):
    vault = copy.deepcopy(student_vault)
    role = vault["experience"][0]
    for index in range(3, 8):
        role["bullets"].append(
            {
                "id": f"bul_exp_001_{index}",
                "text": {"en": f"Extra result {index} with latency {index * 10}ms."},
                "evidence": ["ev_intern"],
            }
        )
    application = _app(vault, tmp_path, "campus", market="cn_internet", persona="student_with_internship", role="Backend Engineer")
    application["selection"]["bullet_ids"] = [b["id"] for b in role["bullets"]]
    with pytest.raises(LayoutError) as error:
        render_application(tmp_path, vault, application)
    assert error.value.code == "layout.budget"


def _user_template(tmp_path: Path, *, omit_slot: bool = False, bad_fingerprint: bool = False) -> str:
    directory = tmp_path / "templates" / "user-test"
    directory.mkdir(parents=True)
    html = '<!doctype html><html><head><link rel="stylesheet" href="styles.css"></head><body><h1 data-slot="identity.name"></h1>'
    if not omit_slot:
        html += '<div data-slot="identity.contact"></div><section data-section="education"><div data-slot="section.education"></div></section>'
    html += "</body></html>"
    (directory / "template.html").write_text(html, encoding="utf-8")
    (directory / "styles.css").write_text("body{font-size:10.5pt}", encoding="utf-8")
    fingerprint = hashlib.sha256((html + "\nbody{font-size:10.5pt}").encode()).hexdigest()
    if bad_fingerprint:
        fingerprint = "0" * 64
    manifest = {
        "id": "user-test",
        "name": "Test",
        "language": "en",
        "version": "1.0.0",
        "status": "private",
        "markets": ["intl_en"],
        "personas": ["experienced"],
        "page": {
            "sizes": ["letter"],
            "margins_mm": {"top": 18, "right": 18, "bottom": 18, "left": 18},
            "target_pages": {"min": 1, "max": 2},
            "columns": "single",
        },
        "slots": {
            "required": [
                {"name": "identity.name", "selector": "[data-slot='identity.name']", "kind": "text"},
                {"name": "identity.contact", "selector": "[data-slot='identity.contact']", "kind": "text"},
                {"name": "section.education", "selector": "[data-slot='section.education']", "kind": "section"},
            ],
            "optional": [],
        },
        "budgets": {
            "summary_chars": {"en": 240, "zh": 120},
            "bullets_per_role": 5,
            "bullets_per_project": 4,
            "max_roles": 5,
            "max_projects": 4,
            "max_skills": 16,
        },
        "files": {"html": "template.html", "css": "styles.css", "preview": "preview.html"},
        "print": {"safe_margin_mm": 12, "bleed_mm": 0, "color_mode": "grayscale_safe"},
        "ats": {"single_column": True, "text_selectable": True, "tables_allowed": False, "standard_headings": ["Education"]},
        "fingerprint": fingerprint,
        "provenance": {"kind": "user_learned", "note": "test"},
    }
    (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return "user-test"


def test_missing_required_slot_is_rejected(tmp_path):
    template_id = _user_template(tmp_path, omit_slot=True)
    with pytest.raises(RenderError) as error:
        load_template(template_id, root=tmp_path)
    assert error.value.code == "render.missing_slot"


def test_fingerprint_mismatch_is_rejected(tmp_path):
    template_id = _user_template(tmp_path, bad_fingerprint=True)
    with pytest.raises(RenderError) as error:
        load_template(template_id, root=tmp_path)
    assert error.value.code == "render.fingerprint_mismatch"


def test_library_manifests_are_valid():
    for template_id in ("ats-classic", "campus", "modern-sidebar", "editorial", "executive", "zh-professional"):
        template = load_template(template_id)
        assert template["manifest"]["fingerprint"] == template["fingerprint"]
        assert (template["directory"] / template["manifest"]["files"]["preview"]).is_file()
        assert template["manifest"]["page"]["sizes"] == ["a4"]
        assert template["manifest"]["language"] in {"zh", "en"}
        assert "size: A4" in template["css"]
        assert "width: 210mm" in template["css"]
        assert "min-height: 297mm" in template["css"]


def _template_dir(template_id: str) -> Path:
    root = Path(__file__).resolve().parents[1] / "templates"
    for folder in ("cn", "en"):
        candidate = root / folder / template_id
        if candidate.is_dir():
            return candidate
    return root / template_id


def test_language_font_stacks_are_separated():
    english = ("ats-classic", "modern-sidebar", "editorial", "executive")
    chinese = ("campus", "zh-professional")
    for template_id in english:
        css = (_template_dir(template_id) / "styles.css").read_text(encoding="utf-8")
        assert "PingFang SC" not in css
        assert "Microsoft YaHei" not in css
        assert "Songti SC" not in css
    for template_id in chinese:
        css = (_template_dir(template_id) / "styles.css").read_text(encoding="utf-8")
        assert any(font in css for font in ("PingFang SC", "Microsoft YaHei", "Source Han Sans SC", "Noto Sans CJK SC"))
