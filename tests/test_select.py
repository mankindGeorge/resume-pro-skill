# SPDX-License-Identifier: MIT
"""Fact selection and ordering tests."""

from __future__ import annotations

import copy

from resume_pro.select import select_facts


def test_student_cn_selection_order_and_facts(student_vault):
    selection = select_facts(
        student_vault,
        market="cn_internet",
        persona="student_with_internship",
        target_role="Backend Engineer",
    )
    sections = {section["id"]: section for section in selection["sections"]}
    assert "job_intent" not in sections
    enabled = [s["id"] for s in sorted(selection["sections"], key=lambda s: s["order"]) if s["enabled"]]
    assert enabled[0] == "education"
    assert enabled.index("education") < enabled.index("skills")
    assert "experience" in enabled
    assert "projects" in enabled
    assert "edu_001" in selection["fact_ids"]
    assert "exp_001" in selection["fact_ids"]
    assert "proj_001" in selection["fact_ids"]
    assert len(selection["bullet_ids"]) == 4
    assert "summary" not in selection  # CN campus order does not include a summary block


def test_selection_drops_extra_bullets(student_vault):
    vault = copy.deepcopy(student_vault)
    role = vault["experience"][0]
    for index in range(3, 7):
        role["bullets"].append(
            {
                "id": f"bul_exp_001_{index}",
                "text": {"en": f"Extra result number {index} with a number {index * 10}."},
                "evidence": ["ev_intern"],
            }
        )
    selection = select_facts(vault, market="cn_internet", persona="student_with_internship", target_role="Backend Engineer")
    assert len([bullet for bullet in selection["bullet_ids"] if bullet.startswith("bul_exp_001")]) <= 4
    assert any("page budget" in item["reason"].lower() for item in selection["dropped"])


def test_page_budget_one_trims_more(student_vault):
    selection = select_facts(
        student_vault,
        market="intl_en",
        persona="experienced",
        target_role="Backend Engineer",
        page_max=1,
    )
    assert len([b for b in selection["bullet_ids"] if b.startswith("bul_exp_")]) <= 3


def test_summary_without_evidence_is_omitted(student_vault):
    vault = copy.deepcopy(student_vault)
    vault["identity"].pop("summary_evidence", None)
    selection = select_facts(vault, market="cn_internet", persona="student_with_internship", target_role="Backend Engineer")
    assert "summary" not in selection
    assert any(item["fact_id"] == "identity.summary" for item in selection["dropped"])


def test_jd_terms_boost_selection(student_vault):
    vault = copy.deepcopy(student_vault)
    role = vault["experience"][0]
    role["bullets"].append(
        {
            "id": "bul_exp_001_jd",
            "text": {"en": "Built a Kafka pipeline that cut latency by 30% for 2M events."},
            "evidence": ["ev_intern"],
        }
    )
    selection = select_facts(
        vault,
        market="cn_internet",
        persona="student_with_internship",
        target_role="Backend Engineer",
        jd_terms={"kafka"},
    )
    assert "bul_exp_001_jd" in selection["bullet_ids"]


def test_sections_include_disabled_optional_sections(student_vault):
    selection = select_facts(student_vault, market="cn_internet", persona="student_with_internship", target_role="Backend Engineer")
    sections = {section["id"]: section for section in selection["sections"]}
    assert sections["awards"]["enabled"] is False
    assert sections["languages"]["enabled"] is False
