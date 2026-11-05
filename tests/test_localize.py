# SPDX-License-Identifier: MIT
"""Transcreation and parity tests."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from resume_pro.application import create_application, page_budget, save_application
from resume_pro.localize import LocalizeError, compare, localize_application
from resume_pro.render import render_application
from resume_pro.select import select_facts


def _source_app(vault, tmp_path, *, market, persona, role, template):
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
    return app


def test_student_zh_to_en_parity_pass(student_vault, tmp_path):
    source = _source_app(
        student_vault,
        tmp_path,
        market="cn_internet",
        persona="student_with_internship",
        role="后端开发工程师（校招）",
        template="campus",
    )
    before = copy.deepcopy(source)
    result = localize_application(
        tmp_path,
        student_vault,
        source,
        target_locale="en",
        target_role="Backend Engineering Intern",
    )
    assert result.parity.status == "pass"
    assert not result.gaps
    assert result.target_market == "intl_en"
    assert result.application["writing"]["locale"] == "en"
    assert result.application["template"]["id"] == "ats-classic"
    assert source == before
    assert result.application["localization"]["source_application"] == source["slug"]


def test_experienced_en_to_zh_parity_pass(experienced_vault, tmp_path):
    source = _source_app(
        experienced_vault,
        tmp_path,
        market="intl_en",
        persona="experienced",
        role="Senior Backend Engineer",
        template="ats-classic",
    )
    result = localize_application(
        tmp_path,
        experienced_vault,
        source,
        target_locale="zh",
        target_role="高级后端工程师",
    )
    assert result.parity.status == "pass"
    assert not result.gaps
    assert result.application["market"] == "cn_internet"
    assert result.application["template"]["id"] == "zh-professional"
    sections = {s["id"]: s for s in result.application["selection"]["sections"]}
    assert sections["summary"]["enabled"] is True
    assert "job_intent" not in sections
    assert sections["education"]["enabled"] is True
    assert sections["experience"]["enabled"] is True


def test_number_unit_conversion_is_parity_clean(student_vault, tmp_path):
    source = _source_app(
        student_vault,
        tmp_path,
        market="cn_internet",
        persona="student_with_internship",
        role="后端开发工程师（校招）",
        template="campus",
    )
    result = localize_application(tmp_path, student_vault, source, target_locale="en", target_role="Backend Intern")
    assert result.parity.number_mismatches == {}


def test_missing_target_locale_raises(student_vault, tmp_path):
    vault = copy.deepcopy(student_vault)
    vault["experience"][0]["bullets"][0]["text"].pop("en")
    source = _source_app(
        vault,
        tmp_path,
        market="cn_internet",
        persona="student_with_internship",
        role="后端开发工程师（校招）",
        template="campus",
    )
    with pytest.raises(LocalizeError) as error:
        localize_application(tmp_path, vault, source, target_locale="en", target_role="Backend Intern")
    assert error.value.code == "localize.locale_gaps"
    assert error.value.details["gaps"][0]["path"] == "experience[0].bullets[0].text"


def test_draft_marks_missing_locale(student_vault, tmp_path):
    vault = copy.deepcopy(student_vault)
    vault["experience"][0]["bullets"][0]["text"].pop("en")
    source = _source_app(
        vault,
        tmp_path,
        market="cn_internet",
        persona="student_with_internship",
        role="后端开发工程师（校招）",
        template="campus",
    )
    result = localize_application(
        tmp_path,
        vault,
        source,
        target_locale="en",
        target_role="Backend Intern",
        draft=True,
    )
    assert result.gaps
    assert result.parity.status == "fail"
    render = render_application(tmp_path, result.render_vault, result.application, draft=True)
    html = Path(render.html_path).read_text(encoding="utf-8")
    assert "[NEEDS EN]" in html
    assert "DRAFT — NOT FOR SUBMISSION" in html


def test_parity_detects_missing_numbers(student_vault, tmp_path):
    source = _source_app(
        student_vault,
        tmp_path,
        market="cn_internet",
        persona="student_with_internship",
        role="后端开发工程师（校招）",
        template="campus",
    )
    target = copy.deepcopy(source)
    target["slug"] = "target"
    target["selection"]["bullet_ids"] = []
    report = compare(student_vault, source, target)
    assert report.status == "fail"
    assert report.number_mismatches
    assert report.bullets_missing


def test_same_locale_is_rejected(student_vault, tmp_path):
    source = _source_app(
        student_vault,
        tmp_path,
        market="cn_internet",
        persona="student_with_internship",
        role="后端开发工程师（校招）",
        template="campus",
    )
    with pytest.raises(LocalizeError) as error:
        localize_application(tmp_path, student_vault, source, target_locale="zh", target_role="后端开发")
    assert error.value.code == "localize.same_locale"


def test_market_language_mismatch_is_rejected(student_vault, tmp_path):
    source = _source_app(
        student_vault,
        tmp_path,
        market="cn_internet",
        persona="student_with_internship",
        role="后端开发工程师（校招）",
        template="campus",
    )
    with pytest.raises(LocalizeError) as error:
        localize_application(
            tmp_path,
            student_vault,
            source,
            target_locale="zh",
            target_market="intl_en",
            target_role="Backend Engineer",
        )
    assert error.value.code in {"localize.same_locale", "localize.market_language_mismatch"}
