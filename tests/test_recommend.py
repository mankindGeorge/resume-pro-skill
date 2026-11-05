# SPDX-License-Identifier: MIT
"""Role-family recommendation tests."""

from __future__ import annotations

import copy

from resume_pro.recommend import recommend


def test_student_recommends_backend_or_ai(student_vault):
    report = recommend(student_vault, market="cn_internet", persona="student_with_internship")
    ids = [family.id for family in report.families]
    assert "backend" in ids or "ai_ml" in ids
    assert len(report.families) == 3
    assert all(family.build_plan for family in report.families)


def test_empty_vault_is_capped(incomplete_vault):
    report = recommend(incomplete_vault, market="cn_internet", persona="student_with_internship")
    assert report.families
    assert any(family.tier == "Not yet" for family in report.families)
    assert any("No experience or project" in note for note in report.notes)


def test_missing_terms_drive_plan(student_vault):
    vault = copy.deepcopy(student_vault)
    report = recommend(vault, market="cn_internet", persona="student_with_internship")
    backend = next(family for family in report.families if family.id == "backend")
    assert backend.missing
    assert any(term in backend.build_plan for term in backend.missing[:2])
