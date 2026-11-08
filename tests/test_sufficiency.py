# SPDX-License-Identifier: MIT
"""Sufficiency gate tests."""

from __future__ import annotations

import copy

import pytest

from resume_pro.errors import GateError
from resume_pro.sufficiency import (
    STATUS_BLOCKED,
    STATUS_MINIMUM,
    STATUS_STRONG,
    ensure_buildable,
    evaluate,
)


def test_student_example_is_strong(student_vault):
    report = evaluate(student_vault, market="cn_internet", persona="student_with_internship", target_role="Backend Engineer")
    assert report.status == STATUS_STRONG
    assert report.can_build
    assert not report.blockers
    assert len(report.dimensions) == 7


def test_student_projects_example_is_strong(student_projects_vault):
    report = evaluate(student_projects_vault, market="cn_internet", persona="student_with_projects", target_role="Backend Engineer")
    assert report.status == STATUS_STRONG


def test_experienced_example_is_strong(experienced_vault):
    report = evaluate(experienced_vault, market="intl_en", persona="experienced", target_role="Senior Backend Engineer")
    assert report.status == STATUS_STRONG
    depth = next(d for d in report.dimensions if d.id == "depth")
    assert depth.status == "pass"


def test_incomplete_vault_is_blocked_with_questions(incomplete_vault):
    report = evaluate(incomplete_vault, market="cn_internet", persona="student_with_internship", target_role="Backend Engineer")
    assert report.status == STATUS_BLOCKED
    codes = {b["code"] for b in report.blockers}
    assert "sufficiency.projects_missing" in codes
    assert report.questions
    assert all("ask" in q and "why" in q for q in report.questions)


def test_missing_projects_blocks(student_vault):
    vault = copy.deepcopy(student_vault)
    vault["projects"] = []
    report = evaluate(vault, market="cn_internet", persona="student_with_internship", target_role="Backend Engineer")
    assert report.status == STATUS_BLOCKED
    assert any(b["code"] == "sufficiency.projects_missing" for b in report.blockers)


def test_no_numbers_gives_minimum_not_blocked(student_vault):
    vault = copy.deepcopy(student_vault)
    for collection in ("experience", "projects"):
        for item in vault[collection]:
            for bullet in item.get("bullets") or []:
                bullet["text"] = {"en": "Worked on the project and improved it."}
    report = evaluate(vault, market="cn_internet", persona="student_with_internship", target_role="Backend Engineer")
    assert report.status == STATUS_MINIMUM
    assert report.can_build
    assert report.requires_confirmation
    assert any(w["code"] == "sufficiency.no_metrics" for w in report.warnings)


def test_cn_campus_without_cs_fundamentals_blocks(student_vault):
    vault = copy.deepcopy(student_vault)
    vault["skills"] = [g for g in vault["skills"] if g.get("kind") != "fundamentals"]
    report = evaluate(vault, market="cn_internet", persona="student_with_internship", target_role="Backend Engineer")
    assert report.status == STATUS_BLOCKED
    assert any(b["code"] == "sufficiency.cs_fundamentals" for b in report.blockers)


def test_missing_target_role_is_a_warning(student_vault):
    report = evaluate(student_vault, market="cn_internet", persona="student_with_internship")
    assert any(w["code"] == "sufficiency.target_role" for w in report.warnings)
    assert report.status == STATUS_MINIMUM


def test_build_mode_is_blocked(incomplete_vault):
    report = evaluate(incomplete_vault, market="cn_internet", persona="student_no_projects", target_role="Backend Engineer")
    assert report.status == STATUS_BLOCKED
    assert any(b["code"] == "sufficiency.build_mode" for b in report.blockers)


def test_draft_label(student_vault):
    report = evaluate(student_vault, market="cn_internet", persona="student_with_internship", target_role="Backend Engineer", draft=True)
    data = report.to_dict()
    assert data["draft"] is True
    assert data["draft_label"] == "DRAFT — NOT FOR SUBMISSION"
    assert data["deliverable"] is False


def test_ensure_buildable_raises_on_blocked(incomplete_vault):
    report = evaluate(incomplete_vault, market="cn_internet", persona="student_with_internship", target_role="Backend Engineer")
    with pytest.raises(GateError) as error:
        ensure_buildable(report)
    assert error.value.code == "gate.blocked"


def test_leadership_scope_gap_advises_not_dead_ends(experienced_vault):
    # senior_manager wants leadership scope, but intake cannot collect team_size/scope;
    # the gap must advise (warning) rather than permanently block the persona.
    for role in experienced_vault.get("experience") or []:
        role.pop("team_size", None)
        role.pop("scope", None)
    report = evaluate(experienced_vault, market="intl_en", persona="senior_manager", target_role="Engineering Manager")
    blocker_codes = {b["code"] for b in report.blockers}
    warning_codes = {w["code"] for w in report.warnings}
    assert "sufficiency.leadership_missing" not in blocker_codes
    assert "sufficiency.leadership_missing" in warning_codes


def test_publications_gap_advises_not_dead_ends(experienced_vault):
    # academic is out of MVP scope and intake collects no publications; the gap
    # must advise rather than permanently block. Research experience stays required.
    experienced_vault["publications"] = []
    experienced_vault.setdefault("projects", []).append(
        {"id": "proj_research", "context": "research", "name": {"en": "Research project"}}
    )
    report = evaluate(experienced_vault, market="intl_en", persona="academic", target_role="Researcher")
    blocker_codes = {b["code"] for b in report.blockers}
    warning_codes = {w["code"] for w in report.warnings}
    assert "sufficiency.publications_missing" not in blocker_codes
    assert "sufficiency.publications_missing" in warning_codes


def test_research_missing_blocker_carries_a_targeted_question(experienced_vault):
    # The academic persona requires research experience. When it is missing the
    # blocker must map to a QUESTION_BANK follow-up, not become a dead end with
    # no way to close the gap.
    vault = copy.deepcopy(experienced_vault)
    vault["projects"] = [p for p in vault.get("projects") or [] if p.get("context") != "research"]
    report = evaluate(vault, market="intl_en", persona="academic", target_role="Researcher")
    assert any(b["code"] == "sufficiency.research_missing" for b in report.blockers)
    questions = [q for q in report.questions if q["code"] == "sufficiency.research_missing"]
    assert questions, "sufficiency.research_missing must map to a QUESTION_BANK entry"
    assert questions[0]["ask"] and questions[0]["why"]
