# SPDX-License-Identifier: MIT
"""Lint and 10-second skim tests."""

from __future__ import annotations

import copy

from resume_pro.lint import lint


def _app(max_pages: int = 2):
    return {
        "page_budget": {"size": "a4", "target": max_pages, "max": max_pages},
        "selection": {"sections": []},
    }


def test_clean_student_has_no_errors(student_vault):
    report = lint(student_vault, market="cn_internet", persona="student_with_internship", application=_app())
    assert report.ok
    assert report.page_estimate >= 1
    assert report.skim.passed


def test_missing_education_is_a_cn_error(student_vault):
    vault = copy.deepcopy(student_vault)
    vault["education"] = []
    report = lint(vault, market="cn_internet", persona="student_with_internship", application=_app())
    assert any(issue.code == "cn.structure_missing_education" for issue in report.errors)


def test_missing_cs_fundamentals_is_an_error(student_vault):
    vault = copy.deepcopy(student_vault)
    vault["skills"] = [group for group in vault["skills"] if group.get("kind") != "fundamentals"]
    report = lint(vault, market="cn_internet", persona="student_with_internship", application=_app())
    assert any(issue.code == "cn.cs_fundamentals_missing" for issue in report.errors)


def test_demo_only_project_is_an_error(student_vault):
    vault = copy.deepcopy(student_vault)
    project = vault["projects"][0]
    project.pop("own_contribution", None)
    project.pop("optimizations", None)
    report = lint(vault, market="cn_internet", persona="student_with_internship", application=_app())
    assert any(issue.code == "cn.demo_only_project" for issue in report.errors)


def test_cliche_and_opening(student_vault):
    vault = copy.deepcopy(student_vault)
    vault["identity"]["summary"] = {"zh": "本人具有良好的沟通能力和团队合作精神。"}
    report = lint(vault, market="cn_internet", persona="student_with_internship", application=_app())
    codes = {issue.code for issue in report.issues}
    assert "cn.cliche_opening" in codes
    assert "cn.cliche" in codes


def test_flow_account_bullet(student_vault):
    vault = copy.deepcopy(student_vault)
    vault["experience"][0]["bullets"].append(
        {"id": "bul_exp_001_flow", "text": {"zh": "负责后端接口开发"}, "evidence": ["ev_intern"]}
    )
    report = lint(vault, market="cn_internet", persona="student_with_internship", application=_app())
    codes = {issue.code for issue in report.issues}
    assert "cn.flow_account" in codes
    assert "lint.weak_verb" in codes


def test_ai_buzzword_density(student_vault):
    vault = copy.deepcopy(student_vault)
    vault["skills"].append(
        {
            "id": "skl_ai_extra",
            "name": {"en": "AI"},
            "kind": "ai_ml",
            "items": [{"name": name, "level": "unknown"} for name in ("LLM", "AIGC", "Prompt", "Transformer", "Agent")],
        }
    )
    report = lint(vault, market="cn_internet", persona="student_with_internship", application=_app())
    assert any(issue.code == "cn.ai_buzzword_density" for issue in report.warnings)


def test_page_count_error(student_vault):
    vault = copy.deepcopy(student_vault)
    role = copy.deepcopy(vault["experience"][0])
    project = copy.deepcopy(vault["projects"][0])
    for index in range(2, 5):
        extra_role = copy.deepcopy(role)
        extra_role["id"] = f"exp_{index:03d}"
        extra_role["company"] = f"Company {index}"
        for b_index, bullet in enumerate(extra_role["bullets"], start=1):
            bullet["id"] = f"bul_exp_{index:03d}_{b_index}"
        vault["experience"].append(extra_role)
        extra_project = copy.deepcopy(project)
        extra_project["id"] = f"proj_{index:03d}"
        extra_project["name"] = f"Project {index}"
        for b_index, bullet in enumerate(extra_project["bullets"], start=1):
            bullet["id"] = f"bul_proj_{index:03d}_{b_index}"
        vault["projects"].append(extra_project)
    report = lint(vault, market="cn_internet", persona="student_with_internship", application=_app(max_pages=1))
    assert any(issue.code == "cn.page_count" for issue in report.errors)


def test_date_order_is_an_error(student_vault):
    vault = copy.deepcopy(student_vault)
    vault["experience"][0]["end"] = "2025-01"
    report = lint(vault, market="cn_internet", persona="student_with_internship", application=_app())
    assert any(issue.code == "lint.date_order" for issue in report.errors)


def test_skim_fails_without_signals(student_vault):
    vault = copy.deepcopy(student_vault)
    vault["skills"] = []
    vault["experience"] = []
    vault["projects"] = []
    report = lint(vault, market="cn_internet", persona="student_with_internship", application=_app())
    assert not report.skim.passed
    assert any(issue.code == "lint.skim_failed" for issue in report.warnings)
