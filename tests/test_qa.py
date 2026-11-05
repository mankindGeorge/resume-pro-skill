# SPDX-License-Identifier: MIT
"""Post-render QA tests."""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import pytest

from resume_pro.application import create_application, page_budget, save_application
from resume_pro.qa import find_browser, run_qa
from resume_pro.render import render_application
from resume_pro.select import select_facts


def _rendered(vault, tmp_path, *, market="cn_internet", persona="student_with_internship", role="Backend Engineer", template="campus"):
    budget = page_budget(market, persona)
    selection = select_facts(vault, market=market, persona=persona, target_role=role, page_max=budget["max"])
    app = create_application(
        vault=vault,
        selection=selection,
        role=role,
        market=market,
        persona=persona,
        framework="result_first",
        company="Example Co",
        template_id=template,
    )
    save_application(tmp_path, app)
    render = render_application(tmp_path, vault, app)
    return app, render


def test_clean_render_has_no_hard_failures(student_vault, tmp_path):
    app, _ = _rendered(student_vault, tmp_path)
    qa = run_qa(tmp_path, student_vault, app)
    assert qa.status in {"pass", "warn"}
    assert not qa.hard_failures
    assert qa.metrics["pages"] >= 1
    assert qa.metrics["font_size_pt"] >= 10


def test_report_contains_no_contact_pii(student_vault, tmp_path):
    app, _ = _rendered(student_vault, tmp_path)
    qa = run_qa(tmp_path, student_vault, app)
    payload = json.dumps(qa.to_dict(), ensure_ascii=False)
    assert "liming@example.com" not in payload
    assert "138 0000 0000" not in payload


def test_missing_output_fails(student_vault, tmp_path):
    budget = page_budget("cn_internet", "student_with_internship")
    selection = select_facts(student_vault, market="cn_internet", persona="student_with_internship", page_max=budget["max"])
    app = create_application(
        vault=student_vault,
        selection=selection,
        role="Backend Engineer",
        market="cn_internet",
        persona="student_with_internship",
        framework="result_first",
        template_id="campus",
    )
    save_application(tmp_path, app)
    qa = run_qa(tmp_path, student_vault, app)
    assert qa.status == "fail"
    assert any(check.id == "qa.output" for check in qa.hard_failures)


def test_missing_bullet_fails(student_vault, tmp_path):
    app, render = _rendered(student_vault, tmp_path)
    html = Path(render.html_path).read_text(encoding="utf-8")
    bullet = student_vault["experience"][0]["bullets"][0]["text"]["zh"]
    assert bullet in html
    Path(render.html_path).write_text(html.replace(bullet, "MISSING_BULLET_TEXT", 1), encoding="utf-8")
    qa = run_qa(tmp_path, student_vault, app)
    assert any(check.id == "qa.parseability.bullets" and check.status == "fail" for check in qa.checks)


def test_font_floor_fails(student_vault, tmp_path):
    app, render = _rendered(student_vault, tmp_path)
    html = Path(render.html_path).read_text(encoding="utf-8")
    assert "--size-body: 10.5pt" in html
    Path(render.html_path).write_text(html.replace("--size-body: 10.5pt", "--size-body: 7pt", 1), encoding="utf-8")
    qa = run_qa(tmp_path, student_vault, app)
    assert any(check.id == "qa.layout.font_size" and check.status == "fail" for check in qa.checks)


def test_sensitive_field_in_intl_fails(experienced_vault, tmp_path):
    app, render = _rendered(
        experienced_vault,
        tmp_path,
        market="intl_en",
        persona="experienced",
        role="Senior Backend Engineer",
        template="ats-classic",
    )
    html = Path(render.html_path).read_text(encoding="utf-8")
    Path(render.html_path).write_text(html.replace("</body>", "<p>Date of Birth: 2000-01</p></body>", 1), encoding="utf-8")
    qa = run_qa(tmp_path, experienced_vault, app)
    assert any(check.id == "qa.market.sensitive" and check.status == "fail" for check in qa.checks)


@pytest.mark.skipif(find_browser() is None, reason="No headless browser available")
def test_page_count_uses_browser_and_can_fail(student_vault, tmp_path):
    app, render = _rendered(student_vault, tmp_path)
    html = Path(render.html_path).read_text(encoding="utf-8")
    match = re.search(r'<section[^>]*data-section="experience"[^>]*>.*?</section>', html, re.DOTALL)
    assert match
    bulk = match.group(0) * 6
    Path(render.html_path).write_text(html.replace("</body>", bulk + "</body>", 1), encoding="utf-8")
    app["page_budget"]["target"] = 1
    app["page_budget"]["max"] = 1
    qa = run_qa(tmp_path, student_vault, app)
    assert qa.browser
    assert qa.metrics["pages"] > 1
    assert any(check.id == "qa.layout.pages" and check.status == "fail" for check in qa.checks)
